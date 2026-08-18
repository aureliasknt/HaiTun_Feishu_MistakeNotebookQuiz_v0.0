"""Shared state, bank and card helpers for Scenario 3 (reactive Q&A + confirm card).

Both ``outreach_confirm_card`` (send the card) and ``outreach_confirm_handle``
(card callback) live on the same two files, and so does the prompt builder's
``literacy_context``:

- ``outreach/state.yaml``  — per-user progress, one row per ``open_id``
- ``outreach/qna_bank.yaml`` — the static answers, composed once from the wiki

Writes are read-modify-write on a file shared with the Scenario 1 producer, so
``update_user`` re-reads immediately before writing and only touches the caller's
own row — never the ``daily`` block the producer owns. The write itself is
atomic (temp file + replace) so a crash cannot leave a half-written campaign.
"""

# The card text is Chinese, where fullwidth colons and question marks are correct.
# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import json
import os
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

# Asia/Shanghai as a fixed offset — no DST since 1991, and no tzdata needed on Windows.
TZ = timezone(timedelta(hours=8), "Asia/Shanghai")

ANSWER_UNDERSTOOD = "understood"
ANSWER_PARTIAL = "partial"
ANSWER_NOT_UNDERSTOOD = "not_understood"
CARD_ANSWERS = (ANSWER_UNDERSTOOD, ANSWER_PARTIAL, ANSWER_NOT_UNDERSTOOD)
HANDLER_NAME = "outreach_confirm"
# tools/_outreach_confirm.py → the agent package root is two parents up.
_PACKAGE_STATE = Path(__file__).resolve().parents[1] / "outreach" / "state.yaml"
# EMA weight for the local familiarity estimate. The authoritative signal stays
# the user profile / supervisor; this is only a cheap in-state approximation.
_EMA_ALPHA = 0.35
_ANSWER_SCORE = {ANSWER_UNDERSTOOD: 1.0, ANSWER_PARTIAL: 0.4, ANSWER_NOT_UNDERSTOOD: 0.0}
_MAX_ANSWERS_KEPT = 200


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(text))
    except TypeError, ValueError:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=TZ)


def user_hash(open_id: str) -> str:
    return hashlib.sha256(open_id.encode("utf-8")).hexdigest()


def qa_id_for(open_id: str, question: str) -> str:
    digest = hashlib.sha256(f"{open_id}\x00{question}".encode()).hexdigest()[:8]
    return f"qa_{datetime.now(TZ):%Y%m%dT%H%M%S}_{digest}"


def error(code: str, message: str, **extra: Any) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message, "retryable": False}, **extra},
        ensure_ascii=False,
    )


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def state_path() -> Path:
    """``OUTREACH_STATE_PATH`` → ``WORKSPACE_DIR/outreach/state.yaml`` → own package.

    The last candidate (``tools/`` → package root → ``outreach/state.yaml``) is what
    lets the campaign run with no env var set, and it must match the mapper's own
    resolution order — the mapper decides who gets an event, these tools decide what
    is written, and disagreeing about which file that is would split the campaign in
    two. Only the *existing* file is returned, so a stray env var pointing nowhere
    does not shadow the real state.
    """
    candidates: list[Path] = []
    explicit = os.environ.get("OUTREACH_STATE_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    workspace = os.environ.get("WORKSPACE_DIR", "").strip()
    if workspace:
        candidates.append(Path(workspace) / "outreach" / "state.yaml")
    candidates.append(_PACKAGE_STATE)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Nothing exists yet: hand back the most specific candidate so the caller's
    # error message names the path it actually looked for.
    return candidates[0]


def read_yaml_mapping(path: Path) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError, yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def write_yaml_mapping(path: Path, data: dict[str, Any]) -> bool:
    """Atomic replace, so a crash mid-write cannot truncate the campaign state."""
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        with suppress(OSError):
            tmp.unlink(missing_ok=True)
        return False
    return True


def bank_path(state: dict[str, Any], state_file: Path) -> Path:
    """``scenario3.qa_bank_path`` — relative to the workspace (state file's parent's parent)."""
    scenario = state.get("scenario3")
    configured = str((scenario or {}).get("qa_bank_path") or "").strip() if isinstance(scenario, dict) else ""
    if not configured:
        return state_file.with_name("qna_bank.yaml")
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    return (state_file.parent.parent / candidate).resolve()


def scenario_config(state: dict[str, Any]) -> dict[str, Any]:
    scenario = state.get("scenario3")
    return scenario if isinstance(scenario, dict) else {}


def find_user(state: dict[str, Any], open_id: str) -> dict[str, Any] | None:
    for user in state.get("users") or []:
        if isinstance(user, dict) and str(user.get("open_id") or "").strip() == open_id:
            return user
    return None


def fresh_user(open_id: str, name: str = "") -> dict[str, Any]:
    """A new target's row: Scenario 3 fields seeded empty, so it starts at the reactive stage.

    The single definition of "what a target row looks like". It has two callers that
    cannot see each other — ``bin/discover_outreach_targets.py`` (an operator filling
    in ids from the org directory) and ``outreach_target_add`` (the controller
    enrolling someone by @-mention) — and a row missing a field is not an error any
    reader would report: ``campaign_turn`` finds the user, grounds the turn, and then
    the counters silently start from whatever ``.get`` defaulted to. Seeding in one
    place is what keeps the two entry points producing the same user.
    """
    return {
        "open_id": open_id,
        "name": name or open_id,
        "stage": "qna_reactive",
        "status": "active",
        "last_message_id": "",
        "last_sent_at": "",
        "node": "",
        "last_qa": {"qa_id": "", "question": "", "keyword": "", "card_message_id": "", "sent_at": ""},
        "answers": [],
        "card_sent_count": 0,
        "confident_streak": 0,
        "confident_count": 0,
        "not_understood_count": 0,
        "familiarity_est": 0.0,
        "handed_off_to_scenario1": False,
        "handed_off_to_scenario2": False,
    }


def controller_open_id(state: dict[str, Any]) -> str:
    """``controller_open_id`` — who may enroll targets. Empty means nobody can.

    Fail-closed on purpose. Enrolling somebody starts a daily DM campaign aimed at
    them, so an empty or missing field must refuse every request rather than allow
    every request — the permissive reading would let any user who reaches the bot
    sign up any colleague they can @.
    """
    return str(state.get("controller_open_id") or "").strip()


def add_target(state_file: Path, open_id: str, name: str = "") -> tuple[str, dict[str, Any] | None]:
    """Enroll *open_id* as a campaign target. Returns ``(action, row)``.

    ``action`` is ``"added"``, ``"already_a_target"`` (nothing written — enrolling
    twice must not reset a user's card history), or a failure reason with ``None``.
    Re-reads immediately before writing for the same reason ``update_user`` does:
    the Scenario 1 producer owns the ``daily`` block in this same file.
    """
    fresh = read_yaml_mapping(state_file)
    if fresh is None:
        return "state_unreadable", None
    existing = find_user(fresh, open_id)
    if existing is not None:
        return "already_a_target", existing
    users = fresh.get("users")
    if not isinstance(users, list):
        users = []
    row = fresh_user(open_id, name)
    users.append(row)
    fresh["users"] = users
    if not write_yaml_mapping(state_file, fresh):
        return "state_write_failed", None
    return "added", row


STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"


def is_paused(user: dict[str, Any]) -> bool:
    """True when this target's row is paused — both scenarios must skip them.

    The single definition of "is this user switched off", because two independent
    readers ask it: ``campaign_turn`` (Scenario 3's grounding + card) and the
    Scenario 1 producer's target list. If they disagreed, a paused user would keep
    getting exactly one of the two, which reads as a half-broken campaign rather
    than a setting.

    ``status`` used to be written by the seed and **read by nothing at all**, so
    setting it to ``paused`` silently did nothing. It is honored now, which is why
    only the explicit ``paused`` value pauses: a missing, empty or unrecognised
    status stays active, so no existing row changes behaviour by being upgraded.
    Pausing keeps the row — the counters and ``answers[]`` are the progress, and
    removing the row to stop the sends would throw that away.
    """
    return str(user.get("status") or STATUS_ACTIVE).strip().casefold() == STATUS_PAUSED


def set_paused(state_file: Path, open_id: str, paused: bool) -> tuple[str, dict[str, Any] | None]:
    """Pause or resume one target. Returns ``(action, row)``.

    ``action`` is ``"paused"`` / ``"resumed"``, ``"already_paused"`` /
    ``"already_active"`` when the row is already in that state (nothing written), or
    a failure reason with ``None``. Only ``status`` is touched: pausing must be
    reversible without costing the user their history.
    """
    fresh = read_yaml_mapping(state_file)
    if fresh is None:
        return "state_unreadable", None
    user = find_user(fresh, open_id)
    if user is None:
        return "not_a_target", None
    if is_paused(user) == paused:
        return ("already_paused" if paused else "already_active"), user
    user["status"] = STATUS_PAUSED if paused else STATUS_ACTIVE
    if not write_yaml_mapping(state_file, fresh):
        return "state_write_failed", None
    return ("paused" if paused else "resumed"), user


def active_open_ids(state: dict[str, Any]) -> list[str]:
    """Every non-paused target's ``open_id`` — Scenario 1's send list.

    Lives here rather than in the producer so "who is switched off" has one answer
    across both scenarios (see :func:`is_paused`).
    """
    out: list[str] = []
    for user in state.get("users") or []:
        if not isinstance(user, dict) or is_paused(user):
            continue
        open_id = user.get("open_id")
        if isinstance(open_id, str) and open_id.strip():
            out.append(open_id.strip())
    return out


def keywords(scenario: dict[str, Any]) -> tuple[str, ...]:
    """``scenario3.keywords``, cleaned. Empty tuple → the campaign matches nothing."""
    raw = scenario.get("keywords") or []
    if not isinstance(raw, list):
        return ()
    return tuple(str(k).strip() for k in raw if isinstance(k, str | int | float) and str(k).strip())


def match_keyword(text: str, configured: tuple[str, ...]) -> str:
    """First configured keyword contained in *text*, case-insensitively, or ``""``.

    The single implementation of the campaign's "is this an agent-literacy question"
    test. It used to live in three places — the channel mapper, the Gateway's
    ``/outreach/ask`` and the answering tool — and a keyword list that agreed in two
    of them decided different things in the third. Now the grounding block is the
    only caller, so a match adds curriculum context to the turn and nothing else.
    """
    lowered = text.casefold()
    return next((k for k in configured if k.casefold() in lowered), "")


def resolve_entry(bank: dict[str, Any], keyword: str) -> tuple[str, dict[str, Any]] | None:
    """Keyword → (canonical name, entry), following one level of ``aliases``."""
    entries = bank.get("qa_bank")
    if not isinstance(entries, dict):
        return None
    key = keyword.strip().casefold()
    if not key:
        return None
    lookup = {str(name).casefold(): str(name) for name in entries}
    if key in lookup:
        name = lookup[key]
        entry = entries.get(name)
        return (name, entry) if isinstance(entry, dict) else None
    aliases = bank.get("aliases")
    if isinstance(aliases, dict):
        for alias, target in aliases.items():
            if str(alias).casefold() != key or not isinstance(target, str):
                continue
            name = lookup.get(target.strip().casefold())
            entry = entries.get(name) if name else None
            return (name or "", entry) if isinstance(entry, dict) else None
    return None


CARD_PROMPT = "这次讲清楚了吗？"


def build_card(qa_id: str) -> str:
    """The confirmation card — one prompt line and three buttons, nothing else.

    The card carries no copy of what it is asking about. It is always sent directly
    after the message it checks (the bank answer on path A/B, the re-explanation on
    path C), so echoing that text back only pushed the buttons down the screen and
    made the user read the same thing twice. What ties a click to an exchange is the
    ``qa_id`` on every button, not visible wording — so the first card and the one
    following a re-explanation are deliberately identical.

    A probe question, when one is due, goes into the answer message instead
    (``probe_for`` / ``answer_with_probe``): it has to be read together with the
    answer it checks, and it is not something the three buttons can answer.
    """
    return json.dumps(
        {
            "config": {"wide_screen_mode": True},
            "elements": [
                {"tag": "markdown", "content": CARD_PROMPT},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 懂了"},
                            "type": "primary",
                            "value": {"action": ANSWER_UNDERSTOOD, "qa_id": qa_id},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🤔 不太懂"},
                            "type": "default",
                            "value": {"action": ANSWER_PARTIAL, "qa_id": qa_id},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 没看懂"},
                            "type": "danger",
                            "value": {"action": ANSWER_NOT_UNDERSTOOD, "qa_id": qa_id},
                        },
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )


PROBE_LEAD = "顺手检验一下："


def probe_for(user: dict[str, Any], scenario: dict[str, Any], entry: dict[str, Any]) -> str:
    """The probe question due on this exchange, or ``""``.

    Every ``card.probe_question_every``-th exchange carries a real question, so a
    claimed "懂了" is not the only evidence. Counted on ``card_sent_count`` *before*
    this exchange increments it: the grounding block is assembled while the model is
    still being prompted, and ``outreach_confirm_card`` only bumps the counter once
    the card is out — so both see the same number for the same exchange.
    """
    card_config = scenario.get("card")
    card_config = card_config if isinstance(card_config, dict) else {}
    every = _as_int(card_config.get("probe_question_every"))
    if every <= 0:
        return ""
    if (_as_int(user.get("card_sent_count")) + 1) % every != 0:
        return ""
    return str(entry.get("probe_question") or "").strip()


def answer_with_probe(answer: str, probe: str) -> str:
    """Put the probe in the answer message, not on the card.

    The card is three buttons about whether the explanation landed; a probe is an
    open question that those buttons cannot answer. It also has to be read next to
    the answer it checks, so it ships with the text and the card stays one line.
    """
    return f"{answer}\n\n{PROBE_LEAD}{probe}" if probe else answer


DEFAULT_AUDIENCE_ROLE = "法务专员 (legal officer)"

DEFAULT_AUDIENCE_STRATEGY: tuple[str, ...] = (
    "先定义, 再机制: 先用一句话说清「这是什么」, 然后才讲它怎么运作 —— 与合同先立定义条款、再写权利义务的读法一致。",
    "类比取自法律而非工程: 固定工作流 ≈ 特别授权 (每一步都被明确限定); 智能体 ≈ 一般授权 "
    "(受托人在授权范围内自行决定步骤); 工具调用 ≈ 受托人代为执行 —— 模型只提出调用, "
    "真正动手的是运行时; 记忆/上下文 ≈ 案卷; 限制与风险 ≈ 免责条款加上尽职核查义务。",
    "讲责任与后果, 不讲架构: 说明「做错了谁承担、如何发现、能否撤回」, 而不是讲模型内部结构。",
    "点明可审计的痕迹: 哪些动作留下记录、哪些能事后举证 —— 这是法务判断一件事能否采用的前提。",
    "避免工程术语; 确有必要时只出现一次, 紧跟一句中文解释 (例: 「token（可粗略理解为字数单位）」)。",
    "边界必须明说: 会编造 (幻觉)、可能泄露资料、不可逆操作要先确认 —— 不确定的地方不许含糊过去。",
    "结论先行, 再用短编号要点展开, 每点一句 —— 按条阅读是这个岗位的习惯。",
)


def audience_block(scenario: dict[str, Any], user: dict[str, Any] | None = None) -> str:
    """The "explain it to this reader" rules — wording is config, not code.

    Scenario 3 teaches one specific audience, and the whole campaign is worth
    nothing if the explanation lands as engineering prose: the reader is a legal
    officer, so an answer that is technically correct and framed as architecture is
    a failed answer. These rules therefore govern **vocabulary, analogy and
    ordering** only.

    They deliberately do *not* set depth, whether to broaden the topic, or how
    hard to push — those stay with the user profile and the background supervisor,
    which decide per user and per turn. Nor do they outrank the user: an explicit
    request in the current message still wins (the injected policy says so). So
    nothing here competes with the existing teaching rules; it only says *in whose
    language* they are carried out.

    Overridable via ``scenario3.audience.role`` / ``.strategy``, and per user via
    the row's own ``role`` — a campaign aimed at a different cohort should not need
    a code change. ``strategy: []`` in config → no block at all.
    """
    config = scenario.get("audience")
    config = config if isinstance(config, dict) else {}
    role = str(config.get("role") or "").strip() or DEFAULT_AUDIENCE_ROLE
    if isinstance(user, dict) and str(user.get("role") or "").strip():
        role = str(user["role"]).strip()

    if "strategy" in config:
        raw = config.get("strategy")
        rules = tuple(str(r).strip() for r in raw if str(r).strip()) if isinstance(raw, list) else ()
    else:
        rules = DEFAULT_AUDIENCE_STRATEGY
    if not rules:
        return ""

    lines = "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, start=1))
    return f"## 讲解对象\n\n对方是**{role}**, 不是工程师。按下列策略组织表达:\n\n{lines}"


def grounding_block(entry: dict[str, Any], canonical: str, probe: str = "") -> str:
    """Curriculum facts for the keyword this turn hit — reference material, not a script.

    Answering used to be a file read: the bank text went to the user verbatim, with
    no model on that path. It is now the *source* the answer is built from, because
    a verbatim bank answer cannot be re-framed for the reader in front of it, and
    the six ``agent-basics`` wiki pages the skill points at do not exist in this
    package — so without this block a bank miss and a bank hit would both be
    answered from general knowledge, unsourced.

    Assembled from files with no model call, so it costs the user nothing. The
    entry's own follow-up wordings are included because the same turn may need to
    re-explain (a card click) and they set the vocabulary for it.
    """
    topic = str(entry.get("topic") or "").strip() or canonical
    parts = [f'<literacy_grounding topic="{topic}" bank_entry="{canonical}">']
    for label, field in (
        ("要点", "summary"),
        ("参考讲法", "answer"),
        ("换个角度", "re_explain"),
        ("最简讲法", "restart"),
    ):
        value = str(entry.get(field) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    if probe:
        parts.append(f"本轮检验题 (拼在答案末尾, 不上卡): {PROBE_LEAD}{probe}")
    parts.append("以上是课程原文, 供你取材与对齐口径 —— **不要照抄**, 按「讲解对象」的策略重新组织表达。")
    parts.append("</literacy_grounding>")
    return "\n".join(parts)


CARD_ACTION_MARKER = "<feishu_card_action>"


def card_click_answer(text: str) -> str:
    """The card answer a ``<feishu_card_action>`` turn carries, or ``""``.

    A click does not arrive as language — Session injects the whole callback as a
    JSON blob, so keyword matching finds nothing in it. Without this, the turn that
    has to re-explain would be the one turn with no curriculum in context.

    Only ``dispatch.handler == "outreach_confirm"`` counts: another card's callback
    is another feature's business.
    """
    if CARD_ACTION_MARKER not in text:
        return ""
    start = text.find(CARD_ACTION_MARKER) + len(CARD_ACTION_MARKER)
    end = text.find("</feishu_card_action>", start)
    body = text[start:end] if end != -1 else text[start:]
    try:
        payload = json.loads(body.strip())
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    dispatch = payload.get("dispatch")
    if not isinstance(dispatch, dict) or dispatch.get("handler") != HANDLER_NAME:
        return ""
    action = payload.get("action")
    value = action.get("value") if isinstance(action, dict) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = None
    answer = str(value.get("action") or "").strip() if isinstance(value, dict) else ""
    return answer if answer in CARD_ANSWERS else ""


def campaign_turn(state: dict[str, Any], state_file: Path, open_id: str, text: str) -> dict[str, Any] | None:
    """Resolve *text* into this campaign's facts, or ``None`` when off-campaign.

    The single answer to "is this turn part of Scenario 3?", because three places
    now ask it: the prompt builder, which injects the audience rules and the
    grounding *before* the model writes; the after-turn hook, which guarantees the
    card *after* it has written; and both of those again on a card click. If they
    disagreed, the hook would either send a card for a turn that was never
    grounded, or skip one that was.

    Two kinds of turn qualify:

    - a **question** whose text hits a configured keyword — the topic comes from
      the keyword;
    - a **card click**, which carries no keyword at all. The topic then comes from
      ``last_qa.keyword``, i.e. the exchange the click is answering, and
      ``card_answer`` says which button it was.

    ``None`` for a disabled campaign, a non-target asker, a **paused** target, a
    message with neither a keyword nor a card answer, or a keyword the bank cannot
    resolve. Each of those is an ordinary conversation and must look like one.

    A paused target is refused here rather than further down on purpose: this is the
    one gate all three Scenario 3 readers share (the prompt builder, the after-turn
    card hook, and the click path), so pausing takes effect on every one of them at
    once — including the click on a card that was already on screen when the pause
    landed. Their row and counters stay untouched; see :func:`is_paused`.
    """
    scenario = scenario_config(state)
    if scenario.get("enabled") is False:
        return None
    user = find_user(state, open_id)
    if user is None or is_paused(user):
        return None

    last_qa = user.get("last_qa") if isinstance(user.get("last_qa"), dict) else {}
    card_answer = card_click_answer(text)
    if card_answer:
        # A click is about the card that is currently open, so that exchange's
        # keyword is the subject — the click itself names no topic.
        keyword = str((last_qa or {}).get("keyword") or "").strip()
    else:
        keyword = match_keyword(text, keywords(scenario))
    if not keyword:
        return None

    bank = read_yaml_mapping(bank_path(state, state_file))
    resolved = resolve_entry(bank, keyword) if isinstance(bank, dict) else None
    if resolved is None:
        return None
    canonical, entry = resolved
    return {
        "scenario": scenario,
        "user": user,
        "keyword": keyword,
        "canonical": canonical,
        "entry": entry,
        "topic": str(entry.get("topic") or "").strip() or canonical,
        "qa_id": str((last_qa or {}).get("qa_id") or ""),
        "card_answer": card_answer,
    }


def suggested_topics(bank: dict[str, Any] | None, exclude_topic: str = "", limit: int = 3) -> list[str]:
    """Curriculum nodes to offer next, skipping the one just covered.

    Taken from the bank so the offer is real: every suggestion is a topic the
    campaign can actually teach, in the order the bank lists them.
    """
    entries = bank.get("qa_bank") if isinstance(bank, dict) else None
    if not isinstance(entries, dict):
        return []
    offers: list[str] = []
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        topic = str(entry.get("topic") or "").strip() or str(name)
        if topic == exclude_topic:
            continue
        label = str(entry.get("summary") or "").strip() or topic
        offers.append(f"{topic} — {label}")
        if len(offers) >= limit:
            break
    return offers


_CARD_ANSWER_INSTRUCTIONS = {
    ANSWER_NOT_UNDERSTOOD: (
        "用户点了「❌ 没看懂」。**从最简单的形式重新开始讲**这同一个知识点: 换最基础的说法, "
        "句子更短, 一次只讲一件事, 不要引入任何新材料, 也不要考问对方。参考上面的「最简讲法」"
        "取材, 但按「讲解对象」的策略自己组织表达。讲完调 outreach_confirm_card 发一张新卡。"
    ),
    ANSWER_PARTIAL: (
        "用户点了「🤔 不太懂」。**换一个角度重讲**这同一个知识点: 换一个不同的类比或例子 —— "
        "不要重复上一条用过的那个 —— 落到对方职业里的具体场景上, 不要引入新材料, 也不要考问对方。"
        "参考上面的「换个角度」取材, 但按「讲解对象」的策略自己组织表达。讲完调 "
        "outreach_confirm_card 发一张新卡。"
    ),
    ANSWER_UNDERSTOOD: (
        "用户点了「✅ 懂了」。这一轮到此结束: 先给一句真诚的肯定 (别浮夸), 然后从下面的候选里"
        "**列出几个新话题**供他挑, 每个一句话说明为什么和他相关, 最后问一句还有没有其他问题。"
        "**不要**发新卡 (没有新说法需要确认), 也不要擅自开始讲下一个话题 —— 讲什么由他决定。"
    ),
}


def card_answer_block(
    answer: str,
    bank: dict[str, Any] | None = None,
    topic: str = "",
    closing_offers: list[str] | None = None,
) -> str:
    """What this turn owes the user, given which button they pressed.

    Every button now gets a written reply instead of pre-composed bank text, so the
    turn needs to be told *which* of the three jobs it is doing. The three are
    deliberately different, and the differences are the teaching design:

    - 没看懂 → start over at the simplest form. No new material, and no quiz: a
      user who just said they are lost needs the explanation, not a test.
    - 不太懂 → same point, different angle, and explicitly a *different* analogy
      from the one that already failed.
    - 懂了 → nothing new is being claimed, so no card. Affirm, offer real next
      topics, and ask if anything else is open; the next subject is the user's
      choice, since this scenario is reactive.
    """
    instruction = _CARD_ANSWER_INSTRUCTIONS.get(answer, "")
    if not instruction:
        return ""
    lines = ["<card_click_response>", instruction]
    if answer == ANSWER_UNDERSTOOD:
        offers = closing_offers if closing_offers is not None else suggested_topics(bank, topic)
        if offers:
            lines.append("可选的新话题 (按需挑 2-3 个, 用他能懂的话说, 不要照抄):")
            lines.extend(f"- {offer}" for offer in offers)
    lines.append("</card_click_response>")
    return "\n".join(lines)


def literacy_context(state: dict[str, Any], state_file: Path, open_id: str, text: str) -> str:
    """Audience rules + curriculum grounding for *text*, or ``""`` when off-campaign.

    On a card click this also carries the per-button instruction, because that turn
    has to *write* the re-explanation now instead of sending pre-composed text.
    """
    turn = campaign_turn(state, state_file, open_id, text)
    if turn is None:
        return ""
    answer = turn.get("card_answer") or ""
    blocks = [
        audience_block(turn["scenario"], turn["user"]),
        grounding_block(turn["entry"], turn["canonical"], probe_for(turn["user"], turn["scenario"], turn["entry"]))
        if not answer
        # A click is not a new exchange: no probe is due on it, and the material is
        # the same point being taught again.
        else grounding_block(turn["entry"], turn["canonical"]),
    ]
    if answer:
        blocks.append(card_answer_block(answer, read_yaml_mapping(bank_path(state, state_file)), turn["topic"]))
    return "\n\n".join(block for block in blocks if block)


DEFAULT_CLOSING = "很好！还有别的想问的吗？"
DEFAULT_CLOSING_DONE = "很好，基础这块你已经过关了！还有别的想问的吗？"


def closing_line(scenario: dict[str, Any], graduated_now: bool = False) -> str:
    """The whole message sent when the user says they understood.

    Not appended to anything: an ``understood`` click ends the exchange, so this is
    the complete reply — an affirmation plus an invitation to ask the next question.
    Scenario 3 is reactive, so the next topic is the user's choice, not ours.

    Overridable via ``scenario3.followup.closing`` / ``closing_done`` so the wording
    is config, not code. Empty string in config → nothing is sent at all.
    """
    followup = scenario.get("followup")
    followup = followup if isinstance(followup, dict) else {}
    key = "closing_done" if graduated_now else "closing"
    if key in followup:
        return str(followup.get(key) or "").strip()
    return DEFAULT_CLOSING_DONE if graduated_now else DEFAULT_CLOSING


def business_context(open_id: str, qa_id: str, keyword: str, topic: str, summary: str) -> str:
    return json.dumps(
        {
            "request_type": HANDLER_NAME,
            "qa_id": qa_id,
            "open_id": open_id,
            "user_hash": user_hash(open_id),
            "topic": topic,
            "keyword_hit": keyword,
            "answer_summary": _clip(summary, 200),
        },
        ensure_ascii=False,
    )


def action_handlers() -> str:
    return json.dumps(dict.fromkeys(CARD_ANSWERS, HANDLER_NAME), ensure_ascii=False)


def update_user(state_file: Path, open_id: str, mutate: Any) -> tuple[dict[str, Any] | None, str]:
    """Re-read, apply *mutate* to this user's row only, write atomically.

    Returns ``(user_row_after, "")`` or ``(None, reason)``. The re-read matters:
    the Scenario 1 producer writes the same file, and a stale in-memory copy would
    silently revert its ``daily`` block.
    """
    fresh = read_yaml_mapping(state_file)
    if fresh is None:
        return None, "state_unreadable"
    user = find_user(fresh, open_id)
    if user is None:
        return None, "not_a_target"
    mutate(user)
    if not write_yaml_mapping(state_file, fresh):
        return None, "state_write_failed"
    return user, ""


def record_answer(user: dict[str, Any], answer: str, qa_id: str, question: str) -> None:
    """Apply one card answer to the user's counters (mutates *user* in place)."""
    answers = user.get("answers")
    if not isinstance(answers, list):
        answers = []
    answers.append({"qa_id": qa_id, "question": _clip(question, 200), "self_assessment": answer, "at": now_iso()})
    user["answers"] = answers[-_MAX_ANSWERS_KEPT:]

    if answer == ANSWER_UNDERSTOOD:
        user["confident_streak"] = _as_int(user.get("confident_streak")) + 1
        user["confident_count"] = _as_int(user.get("confident_count")) + 1
    else:
        user["confident_streak"] = 0
        user["not_understood_count"] = _as_int(user.get("not_understood_count")) + 1

    previous = _as_float(user.get("familiarity_est"))
    score = _ANSWER_SCORE.get(answer, 0.0)
    user["familiarity_est"] = round(previous + _EMA_ALPHA * (score - previous), 4)


def graduated(user: dict[str, Any], state: dict[str, Any]) -> bool:
    """Scenario 3 exit test — enough confident answers AND familiarity at threshold."""
    thresholds = state.get("thresholds")
    thresholds = thresholds if isinstance(thresholds, dict) else {}
    needed = _as_int(thresholds.get("confident_answers_needed")) or 3
    floor = _as_float(thresholds.get("familiarity_done")) or 0.7
    return _as_int(user.get("confident_count")) >= needed and _as_float(user.get("familiarity_est")) >= floor


def _clip(text: str, limit: int) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0
