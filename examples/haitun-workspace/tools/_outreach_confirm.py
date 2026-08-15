"""Shared state, bank and card helpers for Scenario 3 (reactive Q&A + confirm card).

Both ``outreach_confirm_send`` (answer + card) and ``outreach_confirm_handle``
(card callback) live on the same two files:

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


def build_card(question: str, summary: str, qa_id: str, probe: str = "", recheck: bool = False) -> str:
    """The confirmation card — legacy format, one action row of three buttons.

    ``probe`` turns the card into a real check instead of pure self-assessment:
    the question is shown, and the buttons then report how the user feels about it.

    ``recheck`` is the card that follows a re-explanation. It is worded as a second
    attempt ("刚才换了个说法") rather than repeating "你问的是", so a user who is still
    lost is not shown the identical card twice.
    """
    if recheck:
        # The re-explanation was already sent in full as a message; the card only
        # needs enough of it to identify what is being confirmed.
        lines = [f"**刚才换了个说法：**{_clip(summary, 160)}"]
    else:
        lines = [f"**你问的是：**{_clip(question, 120)}", "", f"**答案要点：**{summary}"]
    if probe:
        lines += ["", f"**顺手检验一下：**{probe}"]
    lines += ["", "这次讲清楚了吗？" if recheck else "这样讲清楚了吗？"]
    return json.dumps(
        {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "理解确认"}, "template": "blue"},
            "elements": [
                {"tag": "markdown", "content": "\n".join(lines)},
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
