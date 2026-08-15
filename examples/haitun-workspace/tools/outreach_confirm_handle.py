"""Scenario 3 path C: record a confirmation-card answer and send the follow-up.

The handler behind the card's three buttons (``outreach_confirm``). By the time
this runs the Channel has already replaced the card's buttons with the selected
value, so the click needs no acknowledgement — this only moves the authoritative
state and sends the pre-composed next step from the bank.

The two non-understood answers re-explain **and send a fresh confirmation card**,
because the teaching loop is only closed when the new explanation is itself checked;
otherwise a user who is still lost has no way to say so. ``understood`` closes the
loop instead: an acknowledgement plus an invitation to ask the next question, with
no card, since there is nothing new to confirm.
"""

from __future__ import annotations

import json
from typing import Any

import _outreach_confirm as _oc
from _feishu_impl import send_card_impl as _send_card_impl
from _feishu_impl import send_message_impl as _send_message_impl

# Which bank field answers which button.
_FOLLOWUP_FIELD = {
    _oc.ANSWER_UNDERSTOOD: "next_message",
    _oc.ANSWER_PARTIAL: "re_explain",
    _oc.ANSWER_NOT_UNDERSTOOD: "restart",
}
# Answers whose follow-up is a new explanation → it needs its own confirmation card.
_RECHECK_ANSWERS = (_oc.ANSWER_PARTIAL, _oc.ANSWER_NOT_UNDERSTOOD)


async def outreach_confirm_handle(card_action_json: str = "") -> str:
    """Record one understanding-confirmation answer and send the next teaching step.

    The handler for ``dispatch.handler == "outreach_confirm"`` on cards sent by
    ``outreach_confirm_send``. Session injects the ``<feishu_card_action>`` payload
    as ``card_action_json``; the clicked button's ``qa_id`` and the asker's
    ``open_id`` come from ``action.value`` and ``business_context``, never from
    ``chat_id``.

    The answer updates that user's counters (``confident_streak`` /
    ``confident_count`` / ``not_understood_count`` and the local
    ``familiarity_est`` EMA). With ``scenario3.followup.mode = immediate`` the
    matching bank text is sent as the follow-up: understood → the next node,
    partial → a different angle, not understood → restart from the simplest form.

    A ``qa_id`` that does not match the user's ``last_qa`` is refused without
    writing anything — that is a replayed or stale card, not a new answer.

    After this returns, finish the turn with zero assistant text: the card already
    shows what was picked and the follow-up has been sent. Reply only if this tool
    reports a failure.

    Args:
        card_action_json: The full ``<feishu_card_action>`` JSON (injected by Session).
    """
    if not isinstance(card_action_json, str) or not card_action_json.strip():
        return _oc.error("invalid_argument", "card_action_json is required (pass the <feishu_card_action> payload)")
    try:
        action_payload = json.loads(card_action_json)
    except ValueError as exc:
        return _oc.error("invalid_argument", f"card_action_json is not valid JSON: {exc}")
    if not isinstance(action_payload, dict):
        return _oc.error("invalid_argument", "card_action_json must be a JSON object")

    value = _action_value(action_payload)
    context = action_payload.get("business_context")
    context = context if isinstance(context, dict) else {}

    answer = str(value.get("action") or "").strip()
    if answer not in _oc.CARD_ANSWERS:
        return _oc.error("invalid_argument", f"unknown card action {answer!r}", expected=list(_oc.CARD_ANSWERS))
    qa_id = str(value.get("qa_id") or context.get("qa_id") or "").strip()
    open_id = str(context.get("open_id") or action_payload.get("operator_open_id") or "").strip()
    if not open_id:
        return _oc.error("invalid_argument", "card action carries no open_id (business_context missing?)")

    state_file = _oc.state_path()
    state = _oc.read_yaml_mapping(state_file)
    if state is None:
        return _oc.error("state_unavailable", f"campaign state not readable at {state_file}")
    user = _oc.find_user(state, open_id)
    if user is None:
        return _oc.error("not_a_target", f"{open_id} is not in the campaign", open_id=open_id)

    last_qa = user.get("last_qa")
    last_qa = last_qa if isinstance(last_qa, dict) else {}
    expected_qa = str(last_qa.get("qa_id") or "").strip()
    if not qa_id or (expected_qa and qa_id != expected_qa):
        return _oc.error(
            "stale_card",
            "this card is not the user's current question — not recording it",
            qa_id=qa_id,
            expected_qa_id=expected_qa,
        )

    question = str(last_qa.get("question") or context.get("answer_summary") or "")
    topic = str(last_qa.get("topic") or context.get("topic") or "")
    keyword = str(last_qa.get("keyword") or context.get("keyword_hit") or "")

    def _mutate(row: dict[str, Any]) -> None:
        _oc.record_answer(row, answer, qa_id, question)
        current = row.get("last_qa")
        if isinstance(current, dict):
            current["answered_at"] = _oc.now_iso()
            current["self_assessment"] = answer
        if topic:
            row["node"] = topic

    row, reason = _oc.update_user(state_file, open_id, _mutate)
    if row is None:
        return _oc.error(reason or "state_write_failed", "could not record the answer", open_id=open_id, qa_id=qa_id)

    scenario = _oc.scenario_config(state)
    done = _oc.graduated(row, state)
    followup_text = ""
    followup_sent = False
    recheck_qa_id = ""
    send_error: dict[str, Any] | None = None

    if _followup_immediate(scenario):
        if answer == _oc.ANSWER_UNDERSTOOD:
            # Understood ends the exchange: affirm, then let the user choose what is
            # next. Pushing the following node here would answer a question nobody
            # asked — this scenario is reactive, the user drives it.
            followup_text = _oc.closing_line(scenario, done)
        else:
            followup_text = _followup_text(state, state_file, keyword, answer)
        if followup_text:
            sent = await _send_message_impl(open_id, followup_text, "open_id")
            followup_sent = sent.get("ok") is not False
            if not followup_sent:
                send_error = sent

        # A re-explanation is a new claim to verify → it gets its own card.
        if followup_sent and answer in _RECHECK_ANSWERS and _card_after_every_answer(scenario):
            recheck_qa_id, card_error = await _send_recheck_card(
                state, state_file, open_id, keyword, topic, followup_text, row
            )
            if card_error is not None:
                send_error = send_error or card_error

    if done and str(row.get("stage") or "") == "qna_reactive":
        _oc.update_user(state_file, open_id, lambda r: r.update({"stage": "done"}))

    result: dict[str, Any] = {
        "ok": True,
        "action": answer,
        "qa_id": qa_id,
        "topic": topic,
        "followup_sent": followup_sent,
        "recheck_card_sent": bool(recheck_qa_id),
        "confident_count": row.get("confident_count", 0),
        "confident_streak": row.get("confident_streak", 0),
        "not_understood_count": row.get("not_understood_count", 0),
        "familiarity_est": row.get("familiarity_est", 0.0),
        "stage": "done" if done else row.get("stage", ""),
    }
    if recheck_qa_id:
        result["recheck_qa_id"] = recheck_qa_id
    if done:
        result["handoff_ready"] = "scenario1"
    if send_error is not None:
        result["ok"] = False
        result["followup_error"] = send_error
    return _oc.dumps(result)


async def _send_recheck_card(
    state: dict[str, Any],
    state_file: Any,
    open_id: str,
    keyword: str,
    topic: str,
    explanation: str,
    row: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Ask again about the re-explanation just sent, and make it the user's current qa.

    ``last_qa`` is repointed at the new ``qa_id`` so this card — not the retired one —
    is what the next click validates against.
    """
    qa_id = _oc.qa_id_for(open_id, explanation)
    question = str((row.get("last_qa") or {}).get("question") or "") if isinstance(row.get("last_qa"), dict) else ""
    card = await _send_card_impl(
        open_id,
        _oc.build_card(question or topic, explanation, qa_id, recheck=True),
        "open_id",
        None,
        _oc.business_context(open_id, qa_id, keyword, topic, explanation),
        _oc.action_handlers(),
    )
    if card.get("ok") is False:
        return "", dict(card)

    def _mutate(fresh: dict[str, Any]) -> None:
        fresh["last_qa"] = {
            "qa_id": qa_id,
            "question": question[:200],
            "keyword": keyword,
            "topic": topic,
            "card_message_id": str(card.get("message_id") or ""),
            "sent_at": _oc.now_iso(),
            "recheck": True,
        }
        fresh["card_sent_count"] = int(fresh.get("card_sent_count") or 0) + 1

    _oc.update_user(state_file, open_id, _mutate)
    return qa_id, None


def _card_after_every_answer(scenario: dict[str, Any]) -> bool:
    card = scenario.get("card")
    card = card if isinstance(card, dict) else {}
    return card.get("ask_after_every_answer") is not False


def _action_value(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    value = action.get("value") if isinstance(action, dict) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _followup_immediate(scenario: dict[str, Any]) -> bool:
    followup = scenario.get("followup")
    mode = str((followup or {}).get("mode") or "immediate") if isinstance(followup, dict) else "immediate"
    return mode.strip().casefold() != "next_question"


def _followup_text(state: dict[str, Any], state_file: Any, keyword: str, answer: str) -> str:
    """Pick the pre-composed next step. Nothing is generated here.

    The mapping is unconditional on purpose: 不太懂 always re-explains from a
    different angle, 没看懂 always restarts the node in the simplest language. An
    earlier version swapped in ``probe_question`` after repeated misses, which
    quizzed a user who had just said twice that they were lost — exactly when they
    need the explanation, not a test.
    """
    bank = _oc.read_yaml_mapping(_oc.bank_path(state, state_file))
    resolved = _oc.resolve_entry(bank, keyword) if bank is not None else None
    if resolved is None:
        return ""
    _, entry = resolved
    return str(entry.get(_FOLLOWUP_FIELD[answer]) or "").strip()
