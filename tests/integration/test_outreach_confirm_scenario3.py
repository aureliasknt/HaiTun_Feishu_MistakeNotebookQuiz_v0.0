"""Tests for Scenario 3 — the reactive Q&A + confirmation-card loop.

Three things carry the design and are therefore covered here: the mapper only
emits for a cohort DM that hits a keyword (everything it emits is answered with no
LLM, so a loose filter answers the wrong person), the answer tool writes `last_qa`
only after both sends succeed (it is what silences the background turn), and the
callback refuses a stale `qa_id` instead of recording it against the wrong question.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml

_WORKSPACE = Path(__file__).parents[2] / "examples" / "haitun-workspace"
_MAP = _WORKSPACE / "channel_events" / "feishu" / "agent_literacy_question" / "map.py"
_TOOLS = _WORKSPACE / "tools"


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mapper = _load(_MAP, "agent_literacy_map")


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
        "dedup_window_seconds": 60,
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


def _delivery(text: str, *, open_id: str = "ou_target", chat_type: str = "p2p", msg_type: str = "text") -> dict:
    return {
        "header": {"event_id": "evt_1"},
        "event": {
            "sender": {"sender_id": {"open_id": open_id}, "sender_type": "user"},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "chat_type": chat_type,
                "message_type": msg_type,
                "content": json.dumps({"text": text}),
            },
        },
    }


def _write_campaign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: dict[str, Any]) -> Path:
    outreach = tmp_path / "outreach"
    outreach.mkdir(exist_ok=True)
    state_file = outreach / "state.yaml"
    state_file.write_text(yaml.safe_dump(state, allow_unicode=True), encoding="utf-8")
    (outreach / "qna_bank.yaml").write_text(yaml.safe_dump(_BANK, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(state_file))
    mapper._CACHE["stamp"] = None  # the mtime cache is process-global
    return state_file


# --------------------------------------------------------------------------- mapper


def test_mapper_emits_for_a_cohort_dm_that_hits_a_keyword(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    out = mapper.map_event(_delivery("what is an agent?"))
    assert len(out) == 1
    envelope = out[0]
    assert envelope["event"] == "feishu.agent_literacy.question"
    assert envelope["payload"] == {
        "open_id": "ou_target",
        "text": "what is an agent?",
        "keyword": "agent",
        "message_id": "om_1",
        "chat_id": "oc_1",
    }
    assert envelope["idempotency_key"] == "feishu:agent_literacy:evt_1"
    assert envelope["routing"] == {"open_id": "ou_target"}


@pytest.mark.parametrize(
    "delivery",
    [
        pytest.param(_delivery("今天天气不错"), id="no-keyword"),
        pytest.param(_delivery("what is an agent?", open_id="ou_stranger"), id="not-in-cohort"),
        pytest.param(_delivery("what is an agent?", chat_type="group"), id="group-chat"),
        pytest.param(_delivery("what is an agent?", msg_type="image"), id="not-text"),
    ],
)
def test_mapper_drops_everything_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delivery: dict[str, Any]
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    assert mapper.map_event(delivery) == []


def test_mapper_honours_disabled_and_matches_case_insensitively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    assert mapper.map_event(_delivery("Explain AGENT loops"))[0]["payload"]["keyword"] == "agent"
    _write_campaign(tmp_path, monkeypatch, _state(enabled=False))
    assert mapper.map_event(_delivery("what is an agent?")) == []


def test_mapper_uses_its_own_package_state_without_any_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ordinary bring-up sets no env var, so the shipped state must be found.

    The real `dev-feishu.ps1` exports neither OUTREACH_STATE_PATH nor WORKSPACE_DIR;
    without this fallback the cohort filter silently disappears in production.
    """
    monkeypatch.delenv("OUTREACH_STATE_PATH", raising=False)
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    mapper._CACHE["stamp"] = None
    assert (_WORKSPACE / "outreach" / "state.yaml").resolve() == mapper._PACKAGE_STATE
    assert mapper._state_candidates() == (mapper._PACKAGE_STATE,)

    config = mapper._load_config()
    shipped = yaml.safe_load(mapper._PACKAGE_STATE.read_text(encoding="utf-8"))
    # Keywords and the cohort both come from the shipped file, not the defaults.
    assert config.keywords == tuple(shipped["scenario3"]["keywords"])
    assert config.targets == frozenset(u["open_id"] for u in shipped["users"])


def test_mapper_prefers_the_env_var_over_the_package_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_campaign(tmp_path, monkeypatch, _state(keywords=["kubernetes"]))
    assert mapper._state_candidates()[0] == tmp_path / "outreach" / "state.yaml"
    assert mapper._load_config().keywords == ("kubernetes",)


def test_mapper_falls_back_to_defaults_when_no_state_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing readable anywhere → built-in keywords, and no cohort list to filter on."""
    monkeypatch.setenv("OUTREACH_STATE_PATH", "/nonexistent/state.yaml")
    monkeypatch.setattr(mapper, "_PACKAGE_STATE", Path("/nonexistent/pkg/state.yaml"))
    mapper._CACHE["stamp"] = None
    out = mapper.map_event(_delivery("聊聊智能体", open_id="ou_anyone"))
    assert len(out) == 1
    assert out[0]["payload"]["keyword"] == "智能体"


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
    return stub


def _load_tools() -> tuple[Any, Any]:
    send = _load(_TOOLS / "outreach_confirm_send.py", "outreach_confirm_send_mod")
    handle = _load(_TOOLS / "outreach_confirm_handle.py", "outreach_confirm_handle_mod")
    return send, handle


def _payload(
    text: str = "what is an agent?",
    keyword: str = "agent",
    open_id: str = "ou_target",
) -> str:
    body: dict[str, Any] = {"open_id": open_id, "text": text, "keyword": keyword, "message_id": "om_1"}
    return json.dumps(body)


def _read(state_file: Path) -> dict[str, Any]:
    return yaml.safe_load(state_file.read_text(encoding="utf-8"))


async def test_answer_sends_text_then_card_and_records_last_qa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    send, _ = _load_tools()

    result = json.loads(await send.outreach_confirm_send(_payload()))
    assert result["ok"] is True
    assert result["action"] == "answered"
    assert result["topic"] == "what-is-an-agent"

    # The bank answer goes out as text, the card second, both to the asker's DM.
    assert feishu.texts == [("ou_target", "An agent decides its own next step.")]
    card = feishu.cards[0]
    assert card["receive_id"] == "ou_target"
    assert card["action_handlers"] == {
        "understood": "outreach_confirm",
        "partial": "outreach_confirm",
        "not_understood": "outreach_confirm",
    }
    assert card["business_context"]["qa_id"] == result["qa_id"]
    assert card["business_context"]["open_id"] == "ou_target"
    buttons = card["card"]["elements"][1]["actions"]
    assert [b["value"]["action"] for b in buttons] == ["understood", "partial", "not_understood"]

    user = _read(state_file)["users"][0]
    assert user["last_qa"]["qa_id"] == result["qa_id"]
    assert user["last_qa"]["sent_at"]  # what silences the background LLM turn
    assert user["card_sent_count"] == 1


async def test_answer_reports_bank_miss_without_sending_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A keyword with no entry must stay silent so the LLM path owns the reply."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state(keywords=["agent", "kubernetes"]))
    send, _ = _load_tools()

    result = json.loads(await send.outreach_confirm_send(_payload("how about kubernetes?", "kubernetes")))
    assert result == {"ok": True, "action": "bank_miss", "keyword": "kubernetes"}
    assert feishu.texts == [] and feishu.cards == []
    assert _read(state_file)["users"][0].get("last_qa") is None


async def test_answer_skips_non_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state())
    send, _ = _load_tools()
    result = json.loads(await send.outreach_confirm_send(_payload(open_id="ou_stranger")))
    assert result["action"] == "not_a_target"
    assert feishu.texts == []


async def test_card_failure_is_reported_without_resending_the_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The text already landed: report the partial failure, do not create a duplicate."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    feishu.card_ok = False
    send, _ = _load_tools()

    result = json.loads(await send.outreach_confirm_send(_payload()))
    assert result["ok"] is False
    assert result["action"] == "card_send_failed"
    assert result["answer_sent"] is True
    assert len(feishu.texts) == 1
    # No last_qa → the background turn is free to follow up instead of going quiet.
    assert _read(state_file)["users"][0].get("last_qa") is None


async def test_probe_question_appears_on_every_nth_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state = _state(card={"probe_question_every": 2})
    state["users"][0]["card_sent_count"] = 1
    _write_campaign(tmp_path, monkeypatch, state)
    send, _ = _load_tools()

    await send.outreach_confirm_send(_payload())
    assert "Is a fixed if-else script an agent?" in feishu.cards[0]["card"]["elements"][0]["content"]


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


@pytest.mark.parametrize(
    ("answer", "expected_followup"),
    [
        ("partial", "Another angle: who picks the steps."),
        ("not_understood", "Simplest form: model + tools + loop."),
    ],
)
async def test_a_confused_answer_re_explains_from_the_bank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    feishu: _Feishu,
    helpers: Any,
    answer: str,
    expected_followup: str,
) -> None:
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, answer)))
    assert result["ok"] is True
    assert result["action"] == answer
    assert result["followup_sent"] is True
    assert feishu.texts[0] == ("ou_target", expected_followup)

    user = _read(state_file)["users"][0]
    assert user["answers"][-1]["self_assessment"] == answer
    assert user["not_understood_count"] == 1 and user["confident_streak"] == 0


async def test_understood_sends_only_an_affirmation_and_invitation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Reactive scenario: the user picks what is next, so do not push the next node."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    cards_before = len(feishu.cards)
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["recheck_card_sent"] is False
    assert len(feishu.cards) == cards_before  # no second card
    assert feishu.texts == [("ou_target", helpers.DEFAULT_CLOSING)]
    # The next node must NOT be pushed unasked.
    assert "Next: the agent loop." not in feishu.texts[0][1]

    user = _read(state_file)["users"][0]
    assert user["confident_count"] == 1 and user["confident_streak"] == 1


@pytest.mark.parametrize("answer", ["partial", "not_understood"])
async def test_repeated_confusion_keeps_explaining_instead_of_quizzing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, answer: str
) -> None:
    """A user who already said twice they are lost needs the explanation, not a test.

    An earlier version swapped in ``probe_question`` after two misses, which quizzed
    exactly the person who had just asked for help.
    """
    state = _state()
    state["users"][0]["not_understood_count"] = 2
    _write_campaign(tmp_path, monkeypatch, state)
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    feishu.texts.clear()

    await handle.outreach_confirm_handle(_click(qa_id, answer))
    expected = {
        "partial": "Another angle: who picks the steps.",
        "not_understood": "Simplest form: model + tools + loop.",
    }[answer]
    assert feishu.texts[0] == ("ou_target", expected)
    assert "Is a fixed if-else script an agent?" not in feishu.texts[0][1]


@pytest.mark.parametrize("answer", ["partial", "not_understood"])
async def test_re_explanation_carries_its_own_confirmation_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any, answer: str
) -> None:
    """Without this the loop dead-ends: a still-confused user cannot say so again."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    send, handle = _load_tools()
    first_qa = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]

    result = json.loads(await handle.outreach_confirm_handle(_click(first_qa, answer)))
    assert result["recheck_card_sent"] is True
    recheck_qa = result["recheck_qa_id"]
    assert recheck_qa != first_qa

    card = feishu.cards[-1]
    assert card["business_context"]["qa_id"] == recheck_qa
    assert [b["value"]["action"] for b in card["card"]["elements"][1]["actions"]] == [
        "understood",
        "partial",
        "not_understood",
    ]
    # The wording must differ from the first card, or the user sees the same thing twice.
    assert "刚才换了个说法" in card["card"]["elements"][0]["content"]

    user = _read(state_file)["users"][0]
    assert user["last_qa"]["qa_id"] == recheck_qa
    assert user["last_qa"]["recheck"] is True
    assert user["card_sent_count"] == 2


async def test_the_recheck_card_is_the_one_the_next_click_validates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Clicking the new card works; the retired first card is refused."""
    _write_campaign(tmp_path, monkeypatch, _state())
    send, handle = _load_tools()
    first_qa = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    recheck_qa = json.loads(await handle.outreach_confirm_handle(_click(first_qa, "partial")))["recheck_qa_id"]

    stale = json.loads(await handle.outreach_confirm_handle(_click(first_qa, "understood")))
    assert stale["ok"] is False and stale["error"]["code"] == "stale_card"

    good = json.loads(await handle.outreach_confirm_handle(_click(recheck_qa, "understood")))
    assert good["ok"] is True
    assert good["confident_count"] == 1


async def test_closing_wording_is_configurable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    custom = "太好了, 还想问什么"
    _write_campaign(tmp_path, monkeypatch, _state(followup={"mode": "immediate", "closing": custom}))
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    feishu.texts.clear()

    await handle.outreach_confirm_handle(_click(qa_id, "understood"))
    assert feishu.texts == [("ou_target", custom)]


async def test_closing_can_be_suppressed_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """Empty config → understood sends nothing at all, rather than falling back."""
    _write_campaign(tmp_path, monkeypatch, _state(followup={"mode": "immediate", "closing": ""}))
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["followup_sent"] is False
    assert feishu.texts == []
    assert result["confident_count"] == 1  # still recorded


async def test_no_card_after_re_explanation_when_cards_are_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    _write_campaign(tmp_path, monkeypatch, _state(card={"ask_after_every_answer": False}))
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    cards_before = len(feishu.cards)

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "partial")))
    assert result["recheck_card_sent"] is False
    assert len(feishu.cards) == cards_before


async def test_callback_refuses_a_stale_qa_id_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """A replayed card must not be recorded against the user's current question."""
    state_file = _write_campaign(tmp_path, monkeypatch, _state())
    send, handle = _load_tools()
    await send.outreach_confirm_send(_payload())
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
    _, handle = _load_tools()
    result = json.loads(await handle.outreach_confirm_handle(_click("qa_x", "paham")))
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_argument"


async def test_graduation_flips_stage_to_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state = _state()
    state["users"][0] |= {"confident_count": 2, "familiarity_est": 0.9}
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["stage"] == "done"
    assert result["handoff_ready"] == "scenario1"
    assert _read(state_file)["users"][0]["stage"] == "done"


async def test_next_question_mode_records_without_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    state_file = _write_campaign(tmp_path, monkeypatch, _state(followup={"mode": "next_question"}))
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
    feishu.texts.clear()

    result = json.loads(await handle.outreach_confirm_handle(_click(qa_id, "understood")))
    assert result["followup_sent"] is False
    assert feishu.texts == []
    assert _read(state_file)["users"][0]["confident_count"] == 1


async def test_writes_preserve_the_producer_owned_daily_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feishu: _Feishu, helpers: Any
) -> None:
    """The tools share this file with the Scenario 1 producer; a stale copy would revert it."""
    state = _state()
    state["daily"] = {"next_send_at": "2026-09-01T10:00:00+08:00", "sending": True, "poll_every_minutes": 5}
    state_file = _write_campaign(tmp_path, monkeypatch, state)
    send, handle = _load_tools()
    qa_id = json.loads(await send.outreach_confirm_send(_payload()))["qa_id"]
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


def test_tools_and_mapper_resolve_the_same_state_file(monkeypatch: pytest.MonkeyPatch, helpers: Any) -> None:
    """They must agree: the mapper decides who gets an event, the tools what is written."""
    monkeypatch.delenv("OUTREACH_STATE_PATH", raising=False)
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    mapper._CACHE["stamp"] = None
    assert helpers.state_path() == mapper._PACKAGE_STATE


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
