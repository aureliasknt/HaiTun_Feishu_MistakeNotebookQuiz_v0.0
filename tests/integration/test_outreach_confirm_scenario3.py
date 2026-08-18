"""Tests for Scenario 3 — the reactive Q&A + confirmation-card loop.

The answer itself is written by the model now, so what is testable here is
everything *around* it, and that is where the design lives:

- ``literacy_context`` gives the turn its audience rules and curriculum grounding
  from files alone, and stays silent off-campaign (a non-target, no keyword, a
  disabled campaign) — a block leaking into an ordinary chat would re-frame a reply
  that has nothing to do with the campaign.
- ``outreach_confirm_card`` sends a card identical to the one the removed fast path
  sent, and only points ``last_qa`` at it once the send succeeded.
- the callback refuses a stale ``qa_id`` instead of recording it against the wrong
  question.
"""

# The card wording is Chinese, where the fullwidth question mark is the correct one.
# ruff: noqa: RUF001

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import anyio
import pytest
import yaml

_WORKSPACE = Path(__file__).parents[2] / "examples" / "haitun-workspace"
_TOOLS = _WORKSPACE / "tools"


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helpers(monkeypatch: pytest.MonkeyPatch) -> Any:
    """``_outreach_confirm`` — imported by name, so the tools dir must be importable."""
    monkeypatch.syspath_prepend(str(_TOOLS))
    return _load(_TOOLS / "_outreach_confirm.py", "_outreach_confirm")


def _state(**scenario: Any) -> dict[str, Any]:
    base = {
        "enabled": True,
        "keywords": ["agent", "智能体"],
        "qa_bank_path": "outreach/qna_bank.yaml",
        "followup": {"mode": "immediate"},
        "card": {"probe_question_every": 3},
    }
    return {
        "thresholds": {"familiarity_done": 0.7, "confident_answers_needed": 3},
        "scenario3": base | scenario,
        "users": [{"open_id": "ou_target", "name": "T1", "stage": "qna_reactive"}],
        "daily": {"next_send_at": "", "sending": False},
    }


_BANK = {
    "qa_bank": {
        "agent": {
            "topic": "what-is-an-agent",
            "answer": "An agent decides its own next step.",
            "summary": "agent = tools + loop",
            "next_message": "Next: the agent loop.",
            "re_explain": "Another angle: who picks the steps.",
            "restart": "Simplest form: model + tools + loop.",
            "probe_question": "Is a fixed if-else script an agent?",
        }
    },
    "aliases": {"智能体": "agent"},
}


def _write_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: dict[str, Any], controller: str = ""
) -> Path:
    """Write the campaign files and point the tools at them.

    ``controller`` is only set when given: the enrollment gate fails closed on an
    absent ``controller_open_id``, and that default is itself under test.
    """
    if controller:
        state = state | {"controller_open_id": controller}
    outreach = tmp_path / "outreach"
    outreach.mkdir(exist_ok=True)
    state_file = outreach / "state.yaml"
    state_file.write_text(yaml.safe_dump(state, allow_unicode=True), encoding="utf-8")
    (outreach / "qna_bank.yaml").write_text(yaml.safe_dump(_BANK, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(state_file))
    return state_file


# ------------------------------------------------------------ grounding + audience


def test_grounding_and_audience_reach_the_turn_for_a_cohort_keyword(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers: Any
) -> None:
    """A campaign question must arrive with both the reader's rules and the material.

    This is the whole substitute for the deleted zero-LLM path: the model writes the
    answer, so if either half is missing it answers an unnamed reader from general
    knowledge — the curriculum pages the skill cites are not in this package.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    state = helpers.read_yaml_mapping(state_file)

    block = helpers.literacy_context(state, state_file, "ou_target", "what is an agent?")
    assert "法务" in block or "legal officer" in block
    assert '<literacy_grounding topic="what-is-an-agent"' in block
    assert _BANK["qa_bank"]["agent"]["answer"] in block
    # The follow-up wordings ride along: the same turn may have to re-explain.
    assert _BANK["qa_bank"]["agent"]["re_explain"] in block
    # ...and the model is told to re-frame rather than paste it.
    assert "不要照抄" in block


@pytest.mark.parametrize(
    ("open_id", "text", "scenario", "case"),
    [
        ("ou_stranger", "what is an agent?", {}, "not-a-target"),
        ("ou_target", "今天天气不错", {}, "no-keyword"),
        ("ou_target", "what is an agent?", {"enabled": False}, "campaign-disabled"),
        ("ou_target", "", {}, "empty-text"),
    ],
)
def test_no_block_off_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    helpers: Any,
    open_id: str,
    text: str,
    scenario: dict[str, Any],
    case: str,
) -> None:
    """Off-campaign turns must look untouched — an audience rule would re-frame them."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(**scenario))
    state = helpers.read_yaml_mapping(state_file)
    assert helpers.literacy_context(state, state_file, open_id, text) == "", case


def test_a_keyword_the_bank_cannot_resolve_yields_no_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers: Any
) -> None:
    """A configured keyword with no entry: answer normally rather than half-grounded."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(keywords=["kubernetes"]))
    state = helpers.read_yaml_mapping(state_file)
    assert helpers.literacy_context(state, state_file, "ou_target", "explain kubernetes") == ""


def test_keyword_matching_is_case_insensitive_and_follows_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers: Any
) -> None:
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    state = helpers.read_yaml_mapping(state_file)
    assert helpers.match_keyword("Explain AGENT loops", ("agent",)) == "agent"
    # 智能体 is an alias of the `agent` entry, so it grounds on the same topic.
    block = helpers.literacy_context(state, state_file, "ou_target", "智能体是什么")
    assert 'topic="what-is-an-agent"' in block


def test_the_audience_is_configurable_per_campaign_and_per_user(helpers: Any) -> None:
    """Wording is config: a cohort of a different profession needs no code change."""
    scenario = {"audience": {"role": "财务专员", "strategy": ["只用一个例子"]}}
    block = helpers.audience_block(scenario)
    assert "财务专员" in block and "1. 只用一个例子" in block
    # A row's own role wins over the campaign default.
    assert "法务顾问" in helpers.audience_block(scenario, {"role": "法务顾问"})
    # An empty strategy switches the block off entirely.
    assert helpers.audience_block({"audience": {"strategy": []}}) == ""


def test_the_probe_question_is_flagged_for_the_answer_not_the_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers: Any
) -> None:
    """Every 3rd exchange owes a probe, and it belongs in the text, not on the card."""
    state = _state()
    state["users"][0]["card_sent_count"] = 2  # this exchange is the 3rd
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    loaded = helpers.read_yaml_mapping(state_file)

    block = helpers.literacy_context(loaded, state_file, "ou_target", "what is an agent?")
    assert _BANK["qa_bank"]["agent"]["probe_question"] in block
    assert helpers.PROBE_LEAD in block

    state["users"][0]["card_sent_count"] = 0  # 1st exchange — no probe due
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    loaded = helpers.read_yaml_mapping(state_file)
    assert _BANK["qa_bank"]["agent"]["probe_question"] not in helpers.literacy_context(
        loaded, state_file, "ou_target", "what is an agent?"
    )


# ----------------------------------------------------------------------------- tools


class _Feishu:
    """Stub for ``_feishu_impl`` — records sends instead of calling Feishu."""

    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []
        self.cards: list[dict[str, Any]] = []
        self.card_ok = True

    async def send_message_impl(self, receive_id: str, text: str, receive_id_type: str, on_behalf_of: str = "") -> dict:
        self.texts.append((receive_id, text))
        return {"ok": True, "message_id": f"om_text_{len(self.texts)}"}

    async def send_card_impl(
        self,
        receive_id: str,
        card_json: str,
        receive_id_type: str,
        user_key: Any = None,
        business_context_json: str = "{}",
        action_handlers_json: str = "{}",
        multi_use: bool = False,
    ) -> dict:
        self.cards.append(
            {
                "receive_id": receive_id,
                "card": json.loads(card_json),
                "business_context": json.loads(business_context_json),
                "action_handlers": json.loads(action_handlers_json),
            }
        )
        if not self.card_ok:
            return {"ok": False, "message": "card rejected"}
        return {"ok": True, "message_id": f"om_card_{len(self.cards)}"}


@pytest.fixture
def feishu(monkeypatch: pytest.MonkeyPatch) -> _Feishu:
    """Install the stub before the tool modules import names out of it."""
    stub = _Feishu()
    module = types.ModuleType("_feishu_impl")
    module.send_message_impl = stub.send_message_impl
    module.send_card_impl = stub.send_card_impl
    monkeypatch.setitem(sys.modules, "_feishu_impl", module)
    monkeypatch.syspath_prepend(str(_TOOLS))
    # The after-turn hook imports the card tool by its real name, so that module
    # persists in ``sys.modules`` between tests holding ``send_card_impl`` bound to a
    # *previous* test's stub — its sends then land in an object this test cannot see.
    # Evicting it makes the next import bind this test's stub.
    for cached in ("outreach_confirm_card", "_outreach_confirm"):
        monkeypatch.delitem(sys.modules, cached, raising=False)
    return stub


def _load_tools() -> tuple[Any, Any]:
    card = _load(_TOOLS / "outreach_confirm_card.py", "outreach_confirm_card_mod")
    handle = _load(_TOOLS / "outreach_confirm_handle.py", "outreach_confirm_handle_mod")
    return card, handle


def _click_text(qa_id: str, answer: str, open_id: str = "ou_target") -> str:
    """A click as it reaches the *prompt builder* — Session wraps it in the marker.

    ``_click`` returns the bare payload, which is what Session passes to the tool as
    ``card_action_json``. The turn's user message is the wrapped form, and that is
    what the grounding has to recognise.
    """
    payload = _click(qa_id, answer, open_id)
    return f"<feishu_card_action>\n{payload}\n</feishu_card_action>"


def _read(state_file: Path) -> dict[str, Any]:
    return yaml.safe_load(state_file.read_text(encoding="utf-8"))


async def _send_card(card_mod: Any, **kwargs: Any) -> dict[str, Any]:
    """Send the confirmation card the way a turn does after it has answered."""
    args = {"topic": "what-is-an-agent", "keyword": "agent", "summary": "agent = tools + loop"} | kwargs
    return json.loads(await card_mod.outreach_confirm_card(args.pop("open_id", "ou_target"), **args))


async def test_the_recorded_question_describes_this_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """``answers[]`` must file a self-assessment against what was actually asked.

    Regression: the tool used to copy ``question`` forward from the previous
    ``last_qa``, so after many exchanges the field still held an old question and
    every assessment was recorded against the wrong one. Observed on live state at
    ``card_sent_count: 17``.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()

    first = await _send_card(card_mod, summary="first answer", question="what is an agent?")
    assert _read(state_file)["users"][0]["last_qa"]["question"] == "what is an agent?"

    # A later, different question must not inherit the earlier one.
    await handle.outreach_confirm_handle(_click(first["qa_id"], "understood"))
    second = await _send_card(card_mod, summary="second answer", question="how does tool calling work?")
    assert _read(state_file)["users"][0]["last_qa"]["question"] == "how does tool calling work?"

    # And that is what the callback files against the assessment.
    await handle.outreach_confirm_handle(_click(second["qa_id"], "partial"))
    logged = [a["question"] for a in _read(state_file)["users"][0]["answers"]]
    assert logged == ["what is an agent?", "how does tool calling work?"]


async def test_the_question_falls_back_to_the_summary_then_to_the_previous_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Omitted, it still describes this exchange; a recheck card keeps the original."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()

    await _send_card(card_mod, summary="explained the agent loop")
    assert _read(state_file)["users"][0]["last_qa"]["question"] == "explained the agent loop"

    # Neither given → the exchange is a re-explanation of the same question.
    await _send_card(card_mod, summary="")
    assert _read(state_file)["users"][0]["last_qa"]["question"] == "explained the agent loop"


async def test_the_card_is_identical_to_the_one_the_removed_fast_path_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The callback validates against this shape, so it must not drift from it.

    The model writes the answer now, but it must never write the card: getting the
    ``qa_id``, the three ``value.action`` strings and the handler map right in JSON
    every time is exactly the kind of thing that fails silently — a card whose
    clicks resolve to no handler looks fine until someone presses a button.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()

    result = await _send_card(card_mod)
    assert result["ok"] is True
    assert result["action"] == "card_sent"
    assert result["topic"] == "what-is-an-agent"

    # The answer is the model's own message; this tool sends the card and nothing else.
    assert feishu.texts == []
    card = feishu.cards[0]
    assert card["receive_id"] == "ou_target"
    assert card["action_handlers"] == {
        "understood": "outreach_confirm",
        "partial": "outreach_confirm",
        "not_understood": "outreach_confirm",
    }
    assert card["business_context"]["qa_id"] == result["qa_id"]
    assert card["business_context"]["open_id"] == "ou_target"
    # One prompt line plus the three buttons — nothing else. It sits right under the
    # answer, so repeating the question or a summary on it only made the user read
    # the same text twice and pushed the buttons off the first screen.
    assert card["card"]["elements"][0] == {"tag": "markdown", "content": "这次讲清楚了吗？"}
    assert len(card["card"]["elements"]) == 2
    assert "header" not in card["card"]
    buttons = card["card"]["elements"][1]["actions"]
    assert [b["value"]["action"] for b in buttons] == ["understood", "partial", "not_understood"]
    assert [b["text"]["content"] for b in buttons] == ["✅ 懂了", "🤔 不太懂", "❌ 没看懂"]
    assert {b["value"]["qa_id"] for b in buttons} == {result["qa_id"]}

    user = _read(state_file)["users"][0]
    assert user["last_qa"]["qa_id"] == result["qa_id"]
    assert user["last_qa"]["sent_at"]
    assert user["node"] == "what-is-an-agent"
    assert user["card_sent_count"] == 1


async def test_sending_a_card_makes_it_the_only_answerable_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A second card retires the first — one click must belong to one exchange."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()

    first = await _send_card(card_mod, summary="first exchange")
    second = await _send_card(card_mod, summary="second exchange")
    assert first["qa_id"] != second["qa_id"]
    assert _read(state_file)["users"][0]["last_qa"]["qa_id"] == second["qa_id"]

    stale = json.loads(await handle.outreach_confirm_handle(_click(first["qa_id"], "understood")))
    assert stale["ok"] is False
    assert stale["error"]["code"] == "stale_card"


async def test_card_send_failure_leaves_last_qa_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Never point ``last_qa`` at a card the user never received."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()
    feishu.card_ok = False

    result = await _send_card(card_mod)
    assert result["ok"] is False
    assert result["action"] == "card_send_failed"
    user = _read(state_file)["users"][0]
    assert not (user.get("last_qa") or {}).get("qa_id")
    assert not user.get("card_sent_count")


async def test_no_card_for_a_non_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Outside the cohort the question is answered, but the campaign records nothing."""
    _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()

    result = await _send_card(card_mod, open_id="ou_stranger")
    assert result["action"] == "not_a_target"
    assert feishu.cards == []


async def test_a_disabled_campaign_sends_no_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state(enabled=False))
    card_mod, _ = _load_tools()

    assert (await _send_card(card_mod))["action"] == "disabled"
    assert feishu.cards == []


async def test_open_id_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A card addressed to a ``chat_id`` would ask the wrong place; refuse an empty id."""
    _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()

    result = await _send_card(card_mod, open_id="")
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_argument"
    assert feishu.cards == []


def _click(qa_id: str, answer: str, open_id: str = "ou_target") -> str:
    return json.dumps(
        {
            "schema_version": 2,
            "operator_open_id": open_id,
            "business_context": {
                "request_type": "outreach_confirm",
                "qa_id": qa_id,
                "open_id": open_id,
                "topic": "what-is-an-agent",
                "keyword_hit": "agent",
            },
            "dispatch": {"action_id": answer, "handler": "outreach_confirm", "matched": True},
            "action": {"tag": "button", "value": {"action": answer, "qa_id": qa_id}},
        }
    )


@pytest.mark.parametrize("answer", ["partial", "not_understood"])
async def test_a_confused_click_asks_the_turn_to_re_explain_and_recard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, answer: str
) -> None:
    """The tool records and instructs; it no longer sends the re-explanation itself.

    Three fixed paragraphs cannot re-explain: the second attempt has to differ from
    the first in a way that depends on what was actually said. So the tool returns
    the job and the model writes it.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, answer)))
    assert result["ok"] is True
    assert result["action"] == answer
    assert feishu.texts == [], "the tool must not send the follow-up"
    assert result["next_step"]
    assert result["send_new_card"] is True, "a re-explanation is a new claim to verify"

    user = _read(state_file)["users"][0]
    assert user["answers"][-1]["self_assessment"] == answer
    assert user["not_understood_count"] == 1 and user["confident_streak"] == 0


async def test_the_click_turn_is_grounded_and_told_which_job_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A click carries no keyword, so without this it is the one turn with no material.

    Session injects the callback as a JSON blob, not as language — keyword matching
    finds nothing in it. The subject comes from ``last_qa.keyword`` instead.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    state = helpers.read_yaml_mapping(state_file)

    for answer, must_contain in (
        ("not_understood", "最简单"),
        ("partial", "角度"),
        ("understood", "肯定"),
    ):
        block = helpers.literacy_context(state, state_file, "ou_target", _click_text(qa_id, answer))
        assert "<card_click_response>" in block, answer
        assert must_contain in block, answer
        # The curriculum for the point being re-taught is there too.
        assert _BANK["qa_bank"]["agent"]["answer"] in block, answer
        # Audience rules still apply — the re-explanation is for the same reader.
        assert "法务" in block or "legal officer" in block

    # A probe is not due on a click: it is the same point taught again, not a new one.
    assert _BANK["qa_bank"]["agent"]["probe_question"] not in helpers.literacy_context(
        state, state_file, "ou_target", _click_text(qa_id, "partial")
    )


async def test_understood_offers_real_next_topics_and_no_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Reactive scenario: offer what is next, do not start teaching it."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    cards_before = len(feishu.cards)
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["send_new_card"] is False, "nothing new is claimed, so no card"
    assert len(feishu.cards) == cards_before
    assert feishu.texts == []
    # The instruction names the job; the offer itself is appended when the bank has
    # another topic to give (this one-entry test bank does not — see
    # test_suggested_topics_come_from_the_bank_and_skip_the_current_one).
    assert "新话题" in result["next_step"]
    assert "不要发新卡" in result["next_step"]

    user = _read(state_file)["users"][0]
    assert user["confident_count"] == 1 and user["confident_streak"] == 1


def test_suggested_topics_come_from_the_bank_and_skip_the_current_one(helpers: Any) -> None:
    bank = {
        "qa_bank": {
            "agent": {"topic": "what-is-an-agent", "summary": "S1"},
            "loop": {"topic": "agent-loop", "summary": "S2"},
            "tools": {"topic": "tools-and-tool-calling", "summary": "S3"},
        }
    }
    offers = helpers.suggested_topics(bank, "what-is-an-agent")
    assert [o.split(" — ")[0] for o in offers] == ["agent-loop", "tools-and-tool-calling"]
    assert "S2" in offers[0]
    assert helpers.suggested_topics(None) == []


@pytest.mark.parametrize("answer", ["partial", "not_understood"])
async def test_repeated_confusion_keeps_explaining_instead_of_quizzing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, answer: str
) -> None:
    """A user who already said twice they are lost needs the explanation, not a test."""
    state = _state()
    state["users"][0]["not_understood_count"] = 2
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, answer)))
    assert result["send_new_card"] is True
    block = helpers.literacy_context(
        helpers.read_yaml_mapping(state_file), state_file, "ou_target", _click_text(qa_id, answer)
    )
    assert _BANK["qa_bank"]["agent"]["probe_question"] not in block, "never quiz a lost user"


async def test_a_recheck_card_retires_the_one_before_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The loop only closes if the new explanation is itself checkable."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    first_qa = (await _send_card(card_mod))["qa_id"]
    await handle.outreach_confirm_handle(_click(first_qa, "partial"))

    # The turn re-explains, then sends the fresh card the tool asked for.
    recheck_qa = (await _send_card(card_mod, summary="换个角度再讲一遍"))["qa_id"]
    assert recheck_qa != first_qa
    assert _read(state_file)["users"][0]["last_qa"]["qa_id"] == recheck_qa

    stale = json.loads(await handle.outreach_confirm_handle(_click(first_qa, "understood")))
    assert stale["ok"] is False and stale["error"]["code"] == "stale_card"

    good = json.loads(await handle.outreach_confirm_handle(_click(recheck_qa, "understood")))
    assert good["ok"] is True and good["confident_count"] == 1


async def test_no_new_card_asked_for_when_cards_are_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state(card={"ask_after_every_answer": False}))
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "partial")))
    assert result["send_new_card"] is False


async def test_callback_refuses_a_stale_qa_id_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A replayed card must not be recorded against the user's current question."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    await _send_card(card_mod)
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click("qa_20200101T000000_deadbeef", "understood")))
    assert result["ok"] is False
    assert result["error"]["code"] == "stale_card"
    assert feishu.texts == []
    assert _read(state_file)["users"][0].get("answers") is None


async def test_callback_rejects_an_unknown_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    _card_mod, handle = _load_tools()
    result = json.loads(await handle.outreach_confirm_handle(_click("qa_x", "paham")))
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_argument"


async def test_graduation_flips_stage_to_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state = _state()
    state["users"][0] |= {"confident_count": 2, "familiarity_est": 0.9}
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["stage"] == "done"
    assert result["handoff_ready"] == "scenario1"
    assert _read(state_file)["users"][0]["stage"] == "done"


async def test_the_callback_never_sends_a_message_on_any_button(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Every reply after a click is the model's, so the tool is silent on all three.

    This replaces the old ``followup.mode`` behaviour: ``immediate`` sent the bank's
    text from here, ``next_question`` sent nothing. With no pre-composed text left to
    send, that switch has nothing to select between.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()

    for answer in ("partial", "not_understood", "understood"):
        qa_id = (await _send_card(card_mod, summary=f"answer for {answer}"))["qa_id"]
        feishu.texts.clear()
        result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, answer)))
        assert result["ok"] is True, answer
        assert feishu.texts == [], f"{answer} must not send text from the tool"
        assert result["next_step"], answer

    user = _read(state_file)["users"][0]
    assert len(user["answers"]) == 3
    assert user["confident_count"] == 1


async def test_writes_preserve_the_producer_owned_daily_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The tools share this file with the Scenario 1 producer; a stale copy would revert it."""
    state = _state()
    state["daily"] = {"next_send_at": "2026-09-01T10:00:00+08:00", "sending": True, "poll_every_minutes": 5}
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    await handle.outreach_confirm_handle(_click(qa_id, "understood"))

    assert _read(state_file)["daily"] == state["daily"]


def test_familiarity_ema_moves_toward_the_answer_score(helpers: Any) -> None:
    user: dict[str, Any] = {}
    helpers.record_answer(user, helpers.ANSWER_UNDERSTOOD, "qa_1", "q")
    first = user["familiarity_est"]
    assert 0 < first < 1
    helpers.record_answer(user, helpers.ANSWER_UNDERSTOOD, "qa_2", "q")
    second = user["familiarity_est"]
    assert second > first
    helpers.record_answer(user, helpers.ANSWER_NOT_UNDERSTOOD, "qa_3", "q")
    assert user["familiarity_est"] < second
    assert user["confident_streak"] == 0
    assert user["confident_count"] == 2


def test_the_shipped_state_is_found_with_no_env_var(monkeypatch: pytest.MonkeyPatch, helpers: Any) -> None:
    """The ordinary bring-up sets no env var, so the packaged state must be found.

    `dev-feishu.ps1` exports neither OUTREACH_STATE_PATH nor WORKSPACE_DIR. Without
    this fallback the campaign silently has no cohort in production: every reader
    would resolve a different file, or none.
    """
    monkeypatch.delenv("OUTREACH_STATE_PATH", raising=False)
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    assert helpers.state_path() == helpers._PACKAGE_STATE
    assert (_WORKSPACE / "outreach" / "state.yaml").resolve() == helpers._PACKAGE_STATE


def test_tools_ignore_an_env_var_pointing_at_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers: Any
) -> None:
    """A stale env var must not shadow the real shipped state."""
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(tmp_path / "missing" / "state.yaml"))
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    assert helpers.state_path() == helpers._PACKAGE_STATE


def test_alias_keywords_resolve_to_the_canonical_entry(helpers: Any) -> None:
    assert helpers.resolve_entry(_BANK, "智能体")[0] == "agent"
    assert helpers.resolve_entry(_BANK, "AGENT")[0] == "agent"
    assert helpers.resolve_entry(_BANK, "kubernetes") is None


# ----------------------------------------------------- the card guarantee (after_turn)
#
# Deleting the ``fire=tool`` trigger removed the *mechanical* guarantee that a card
# follows every answer: that trigger fired on message arrival, which cannot work once
# the answer is written by the model. ``system_after_turn`` restores it at the only
# point where it can live — after the answer is committed. These tests cover the part
# that is easy to get wrong: not sending a second card when the turn already sent one.


@pytest.fixture
def sys_module(monkeypatch: pytest.MonkeyPatch, feishu: _Feishu) -> Any:
    """``systems/system.py`` with the tools dir importable (it imports by name)."""
    monkeypatch.syspath_prepend(str(_WORKSPACE / "systems"))
    monkeypatch.syspath_prepend(str(_TOOLS))
    return _load(_WORKSPACE / "systems" / "system.py", "haitun_system")


def _ws(tmp_path: Path, open_id: str = "ou_target") -> Any:
    """A per-user workspace dir — the hook reads the identity from its name."""
    path = tmp_path / open_id
    path.mkdir(exist_ok=True)
    return anyio.Path(str(path))


async def test_the_hook_sends_the_card_the_turn_forgot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """A grounded answer with no card must not end without one."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())

    # The prompt builder records the pre-turn qa_id; the turn then answers and
    # (wrongly) never calls outreach_confirm_card.
    assert sys_module._literacy_context(_ws(tmp_path), "what is an agent?") != ""
    await sys_module._ensure_confirmation_card(
        _ws(tmp_path), "what is an agent?", "智能体就是自己决定下一步的系统。它和固定流程的区别在于……"
    )

    assert len(feishu.cards) == 1, "the hook must supply the missing card"
    row = _read(state_file)["users"][0]
    assert row["last_qa"]["qa_id"]
    assert row["last_qa"]["question"] == "what is an agent?"
    # The summary comes from the model's own opening sentence.
    assert row["last_qa"]["summary"].startswith("智能体就是自己决定下一步的系统。")
    assert row["card_sent_count"] == 1


async def test_the_hook_stands_down_when_the_turn_sent_its_own_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """Exactly one card per exchange — a second would retire the first one's qa_id.

    Decided from state (the qa_id changed), never from elapsed time: this campaign
    already had a seconds-window guard and it was a guess about timing.
    """
    _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()

    sys_module._literacy_context(_ws(tmp_path), "what is an agent?")
    await _send_card(card_mod, question="what is an agent?")  # the turn behaves
    assert len(feishu.cards) == 1

    await sys_module._ensure_confirmation_card(_ws(tmp_path), "what is an agent?", "已经答过并发过卡了。")
    assert len(feishu.cards) == 1, "the hook must not add a second card"


@pytest.mark.parametrize(
    ("text", "answer", "case"),
    [
        ("今天天气不错", "天气不错啊。", "off-campaign question"),
        ("what is an agent?", "", "empty answer"),
    ],
)
async def test_the_hook_sends_nothing_when_no_card_is_owed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    feishu: _Feishu,
    helpers: Any,
    sys_module: Any,
    text: str,
    answer: str,
    case: str,
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    sys_module._literacy_context(_ws(tmp_path), text)
    await sys_module._ensure_confirmation_card(_ws(tmp_path), text, answer)
    assert feishu.cards == [], case


async def test_an_ungrounded_turn_is_never_given_a_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """No recorded pre-turn id → the builder never grounded it, so nothing is owed.

    This is what stops a later ordinary message from inheriting an earlier campaign
    turn's obligation and sending a card nobody asked for.
    """
    _write_campaign(tmp_path, monkeypatch, _state())

    # A campaign turn grounds and is served, clearing the record...
    sys_module._literacy_context(_ws(tmp_path), "what is an agent?")
    await sys_module._ensure_confirmation_card(_ws(tmp_path), "what is an agent?", "答案。")
    feishu.cards.clear()

    # ...and the same text arriving without a build step gets no card.
    await sys_module._ensure_confirmation_card(_ws(tmp_path), "what is an agent?", "又答了一次。")
    assert feishu.cards == []


async def test_the_hook_sends_no_card_after_understood(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """懂了 owes no card, so the guarantee must not "restore" one.

    Regression: the hook treated "grounded turn, no new card" as a lapse to repair.
    On a 懂了 click that is the *correct* outcome — the turn affirms and offers next
    topics, claiming nothing new — so the hook was handing the user
    「这次讲清楚了吗？」 about a message that taught nothing.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    cards_after_initial = len(feishu.cards)

    click = _click_text(qa_id, "understood")
    sys_module._literacy_context(_ws(tmp_path), click)
    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["send_new_card"] is False

    await sys_module._ensure_confirmation_card(
        _ws(tmp_path), click, "很好！你抓住重点了。接下来可以看：智能体循环。还有别的想问的吗？"
    )
    assert len(feishu.cards) == cards_after_initial, "no card may follow 懂了"
    assert _read(state_file)["users"][0]["card_sent_count"] == 1


@pytest.mark.parametrize("answer", ["partial", "not_understood"])
async def test_the_hook_still_covers_a_forgotten_recheck_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any, answer: str
) -> None:
    """The 懂了 exemption must not switch the guarantee off for the other two."""
    _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, handle = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    cards_after_initial = len(feishu.cards)

    click = _click_text(qa_id, answer)
    sys_module._literacy_context(_ws(tmp_path), click)
    await handle.outreach_confirm_handle(_click(qa_id, answer))
    # The turn re-explains but forgets the fresh card; the hook supplies it.
    await sys_module._ensure_confirmation_card(_ws(tmp_path), click, "换个说法再讲一遍：……")
    assert len(feishu.cards) == cards_after_initial + 1, answer


async def test_the_injector_and_the_helper_produce_the_same_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """``system.py`` must delegate assembly, not keep its own copy of it.

    Regression: it briefly had an inlined copy of the block assembly. The copy went
    stale the moment the card-click instruction was added to the helper, so clicks
    reached the model with no instruction — while the tests, which exercise the
    helper, kept passing. Comparing the two is what makes that undetectable drift
    detectable.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    state = helpers.read_yaml_mapping(state_file)

    for text in ("what is an agent?", _click_text(qa_id, "partial")):
        assert sys_module._literacy_context(_ws(tmp_path), text) == helpers.literacy_context(
            state, state_file, "ou_target", text
        )


async def test_a_click_turn_is_grounded_through_the_injector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """The click instruction has to survive the path the runtime actually uses."""
    _write_campaign(tmp_path, monkeypatch, _state())
    card_mod, _ = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]

    for answer, marker in (("not_understood", "最简单"), ("partial", "角度"), ("understood", "肯定")):
        block = sys_module._literacy_context(_ws(tmp_path), _click_text(qa_id, answer))
        assert "<card_click_response>" in block, answer
        assert marker in block, answer


async def test_enrolling_by_mention_writes_a_full_target_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The controller @-s somebody and they become a target, seeded to start reactive.

    The row has to be *complete*: an incomplete one still matches ``campaign_turn``,
    so the campaign would ground their turns while the counters start from whatever
    ``.get`` defaulted to — a broken user that looks enrolled.
    """
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    result = json.loads(
        await add_mod.outreach_target_add(["ou_new"], caller_open_id="ou_boss", names=["张三"])
    )
    assert result["ok"] is True
    assert result["added"] == [{"open_id": "ou_new", "name": "张三"}]

    row = helpers.find_user(_read(state_file), "ou_new")
    assert row == helpers.fresh_user("ou_new", "张三")
    assert row["stage"] == "qna_reactive"
    # Enrolling sends nothing — Scenario 3 waits for them to ask.
    assert feishu.cards == [] and feishu.texts == []
    assert "next_step" in result


async def test_only_the_controller_may_enroll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    """Being enrolled means daily DMs from a bot, so a stranger's request writes nothing."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    result = json.loads(await add_mod.outreach_target_add(["ou_victim"], caller_open_id="ou_stranger"))
    assert result["ok"] is False
    assert result["error"]["code"] == "not_authorized"
    assert _read(state_file)["users"] == _state()["users"]


async def test_an_unset_controller_refuses_everyone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    """Fail closed: the permissive reading would let anyone enroll anyone."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())  # no controller_open_id
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    result = json.loads(await add_mod.outreach_target_add(["ou_new"], caller_open_id="ou_anybody"))
    assert result["ok"] is False
    assert result["error"]["code"] == "not_configured"
    assert _read(state_file)["users"] == _state()["users"]


async def test_enrolling_an_existing_target_keeps_their_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    """Re-adding must not reset card history — the row is progress, not a registration."""
    state = _state()
    state["users"][0] |= {"card_sent_count": 7, "confident_count": 2, "familiarity_est": 0.55}
    state_file = _write_campaign(tmp_path, monkeypatch, state, controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    result = json.loads(await add_mod.outreach_target_add(["ou_target"], caller_open_id="ou_boss"))
    assert result["already_a_target"] == ["ou_target"]
    assert result["added"] == []
    row = _read(state_file)["users"][0]
    assert (row["card_sent_count"], row["confident_count"], row["familiarity_est"]) == (7, 2, 0.55)


async def test_a_chat_id_is_rejected_without_blocking_the_valid_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """``oc_...`` can never match a DM sender, so it is refused — by name, and alone."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    result = json.loads(await add_mod.outreach_target_add(["oc_group", "ou_ok"], caller_open_id="ou_boss"))
    assert result["ok"] is False
    assert [r["open_id"] for r in result["rejected"]] == ["oc_group"]
    # Partial success is still honest: the valid id got in.
    assert result["added"] == [{"open_id": "ou_ok", "name": "ou_ok"}]
    assert helpers.find_user(_read(state_file), "ou_ok") is not None


async def test_enrollment_needs_both_ids_and_a_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    """No caller means nothing to authorize against — refuse rather than assume."""
    _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    for open_ids, caller in (([], "ou_boss"), (["ou_new"], "")):
        result = json.loads(await add_mod.outreach_target_add(open_ids, caller_open_id=caller))
        assert result["error"]["code"] == "invalid_argument", (open_ids, caller)


async def test_an_enrolled_target_is_grounded_on_their_next_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The point of enrolling: the campaign must actually pick them up afterwards."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    add_mod = _load(_TOOLS / "outreach_target_add.py", "outreach_target_add_mod")

    def _block() -> str:
        state = helpers.read_yaml_mapping(state_file)
        return helpers.literacy_context(state, state_file, "ou_new", "what is an agent?")

    assert _block() == ""
    await add_mod.outreach_target_add(["ou_new"], caller_open_id="ou_boss", names=["张三"])
    assert '<literacy_grounding topic="what-is-an-agent"' in _block()


async def test_pausing_stops_scenario_3_but_keeps_every_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The whole point of a pause: the sends stop, the learning history does not.

    Removing the row was the only stop available before, and the row *is* the
    progress — so this asserts both halves, not just the silence.
    """
    state = _state()
    state["users"][0] |= {"card_sent_count": 9, "confident_count": 2, "familiarity_est": 0.61}
    state_file = _write_campaign(tmp_path, monkeypatch, state, controller="ou_boss")
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")

    def _block() -> str:
        return helpers.literacy_context(helpers.read_yaml_mapping(state_file), state_file, "ou_target", "what is an agent?")

    assert _block() != ""  # grounded before the pause
    result = json.loads(await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_boss"))
    assert result["ok"] is True and result["changed"] == ["ou_target"]

    assert _block() == ""  # no grounding, so no answer framing and no card
    row = helpers.find_user(_read(state_file), "ou_target")
    assert (row["card_sent_count"], row["confident_count"], row["familiarity_est"]) == (9, 2, 0.61)
    assert row["status"] == "paused"
    # Nobody is told they were paused.
    assert feishu.cards == [] and feishu.texts == []


async def test_resuming_restores_the_campaign_from_where_it_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state = _state()
    state["users"][0] |= {"status": "paused", "card_sent_count": 4}
    state_file = _write_campaign(tmp_path, monkeypatch, state, controller="ou_boss")
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")

    result = json.loads(
        await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_boss", paused=False)
    )
    assert result["action"] == "resumed" and result["changed"] == ["ou_target"]

    state_after = helpers.read_yaml_mapping(state_file)
    block = helpers.literacy_context(state_after, state_file, "ou_target", "what is an agent?")
    assert '<literacy_grounding topic="what-is-an-agent"' in block
    assert helpers.find_user(state_after, "ou_target")["card_sent_count"] == 4


async def test_a_paused_target_is_dropped_from_the_daily_send_list(helpers: Any) -> None:
    """Scenario 1 must honour the same pause — otherwise the daily DM still lands."""
    state = {
        "users": [
            {"open_id": "ou_a"},
            {"open_id": "ou_b", "status": "paused"},
            {"open_id": "ou_c", "status": "active"},
        ]
    }
    assert helpers.active_open_ids(state) == ["ou_a", "ou_c"]


def test_only_the_explicit_paused_value_pauses(helpers: Any) -> None:
    """``status`` was read by nothing before, so upgrading must not pause anybody.

    A missing, empty or unrecognised value has to stay active — every existing row
    in a live campaign predates this field being honoured.
    """
    assert helpers.is_paused({}) is False
    assert helpers.is_paused({"status": ""}) is False
    assert helpers.is_paused({"status": "active"}) is False
    assert helpers.is_paused({"status": "zzz"}) is False
    # Case and stray whitespace are the operator's typing, not a different intent.
    assert helpers.is_paused({"status": "paused"}) is True
    assert helpers.is_paused({"status": " Paused "}) is True


async def test_a_click_on_a_card_sent_before_the_pause_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A card already on screen when the pause landed must not keep teaching."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    card_mod, handle_mod = _load_tools()
    qa_id = (await _send_card(card_mod))["qa_id"]
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")
    await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_boss")

    # The click carries no keyword, so the grounding comes from last_qa — and a
    # paused row must stop that too, not just fresh questions.
    assert helpers.literacy_context(
        helpers.read_yaml_mapping(state_file), state_file, "ou_target", _click_text(qa_id, "partial")
    ) == ""


async def test_pausing_needs_the_controller_and_real_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Resuming restarts daily DMs, so both directions sit behind the same gate."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")

    refused = json.loads(await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_stranger"))
    assert refused["error"]["code"] == "not_authorized"
    assert helpers.is_paused(helpers.find_user(_read(state_file), "ou_target")) is False

    for open_ids, caller in (([], "ou_boss"), (["ou_target"], "")):
        result = json.loads(await pause_mod.outreach_target_pause(open_ids, caller_open_id=caller))
        assert result["error"]["code"] == "invalid_argument", (open_ids, caller)


async def test_pausing_a_non_target_is_reported_not_invented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    """Somebody who was never enrolled has nothing to pause — say so."""
    _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")

    result = json.loads(await pause_mod.outreach_target_pause(["ou_nobody"], caller_open_id="ou_boss"))
    assert result["ok"] is False
    assert result["failed"] == [{"open_id": "ou_nobody", "reason": "not_a_target"}]


async def test_pausing_twice_writes_nothing_the_second_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state(), controller="ou_boss")
    pause_mod = _load(_TOOLS / "outreach_target_pause.py", "outreach_target_pause_mod")

    await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_boss")
    again = json.loads(await pause_mod.outreach_target_pause(["ou_target"], caller_open_id="ou_boss"))
    assert again["ok"] is True
    assert again["changed"] == []
    assert [u["open_id"] for u in again["unchanged"]] == ["ou_target"]


async def test_a_non_dm_workspace_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, sys_module: Any
) -> None:
    """Group chats, the SPA and the CLI have no ``ou_`` workspace — and no cohort row."""
    _write_campaign(tmp_path, monkeypatch, _state())
    group = tmp_path / "chat-oc_1"
    group.mkdir()
    assert sys_module._literacy_context(anyio.Path(str(group)), "what is an agent?") == ""
    await sys_module._ensure_confirmation_card(anyio.Path(str(group)), "what is an agent?", "答案。")
    assert feishu.cards == []
