"""Scenario 3: record a confirmation-card answer. The reply itself is the model's.

The handler behind the card's three buttons (``outreach_confirm``). By the time this
runs the Channel has already replaced the card's buttons with the selected value, so
the click needs no acknowledgement.

This tool used to *send* the follow-up too, picking pre-composed text out of the
bank: ``restart`` for 没看懂, ``re_explain`` for 不太懂, a fixed closing line for
懂了. It no longer sends anything. Three fixed paragraphs cannot re-explain — the
second attempt has to differ from the first in a way that depends on what was
actually said, and a fixed string cannot know that. So the tool keeps what only it
can do (the ``qa_id`` gate, the counters, the EMA, graduation) and returns
``next_step``: the job this turn owes the user, which the model then writes.

The division of the three answers is unchanged, because it is the teaching design:
the two non-understood answers re-explain **and get a fresh card**, since a new
explanation is a new claim and a user who is still lost needs a way to say so;
懂了 ends the exchange with an affirmation, real next-topic offers and an open
question, and **no** card, because nothing new is being claimed.
"""

from __future__ import annotations

import json
from typing import Any

import _outreach_confirm as _oc

# Answers whose follow-up is a new explanation → it needs its own confirmation card.
_RECHECK_ANSWERS = (_oc.ANSWER_PARTIAL, _oc.ANSWER_NOT_UNDERSTOOD)

# What the turn owes the user, per button. Short on purpose: the full instruction and
# the curriculum are already in this turn's prompt (``_outreach_confirm`` →
# ``card_answer_block``); this is the tool result restating the job so a turn that
# skimmed the prompt still cannot get it wrong.
_INSTRUCTIONS = {
    _oc.ANSWER_NOT_UNDERSTOOD: (
        "从最简单的形式重新讲这同一点 (不引入新材料, 不考问), 然后调 outreach_confirm_card 发新卡。"
    ),
    _oc.ANSWER_PARTIAL: (
        "换一个类比/例子重讲这同一点 (不要重复上次那个, 不引入新材料), 然后调 outreach_confirm_card 发新卡。"
    ),
    _oc.ANSWER_UNDERSTOOD: (
        "先一句真诚的肯定, 再列几个新话题供他挑 (每个一句话说明相关性), 最后问还有没有其他问题。不要发新卡。"
    ),
}


async def outreach_confirm_handle(card_action_json: str = "") -> str:
    """Record one understanding-confirmation answer, then write the reply yourself.

    The handler for ``dispatch.handler == "outreach_confirm"`` on cards sent by
    ``outreach_confirm_card``. Session injects the ``<feishu_card_action>`` payload
    as ``card_action_json``; the clicked button's ``qa_id`` and the asker's
    ``open_id`` come from ``action.value`` and ``business_context``, never from
    ``chat_id``.

    Call this **first**, before writing anything: it updates that user's counters
    (``confident_streak`` / ``confident_count`` / ``not_understood_count`` and the
    local ``familiarity_est`` EMA) and decides graduation. A ``qa_id`` that does not
    match the user's ``last_qa`` is refused without writing anything — that is a
    replayed or stale card, not a new answer.

    It sends **no message**. The reply is yours to write, and the result says which
    of the three jobs this is:

    - ``next_step`` — what this turn owes the user, in words. The same instruction is
      in your prompt (``<card_click_response>``) along with the curriculum for the
      point being re-taught.
    - ``send_new_card`` — ``true`` for 不太懂 / 没看懂: your re-explanation is a new
      claim, so finish by calling ``outreach_confirm_card``. ``false`` for 懂了,
      which asserts nothing new and therefore ends without a card.

    Do not restate the click ("你点了…") — the card already shows what was picked.

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

    if done and str(row.get("stage") or "") == "qna_reactive":
        _oc.update_user(state_file, open_id, lambda r: r.update({"stage": "done"}))

    # What this turn owes the user, in words — the tool no longer sends it. The
    # click's grounding is already in this turn's prompt, so this only names the job.
    instruction = _INSTRUCTIONS[answer]
    if answer == _oc.ANSWER_UNDERSTOOD:
        offers = _oc.suggested_topics(_oc.read_yaml_mapping(_oc.bank_path(state, state_file)), topic)
        if offers:
            instruction += " 可选的新话题: " + "; ".join(offers)
        if done:
            instruction += " 他已经过关了, 肯定的话里可以点明这一点。"

    result: dict[str, Any] = {
        "ok": True,
        "action": answer,
        "qa_id": qa_id,
        "topic": topic,
        "next_step": instruction,
        "send_new_card": answer in _RECHECK_ANSWERS and _card_after_every_answer(scenario),
        "confident_count": row.get("confident_count", 0),
        "confident_streak": row.get("confident_streak", 0),
        "not_understood_count": row.get("not_understood_count", 0),
        "familiarity_est": row.get("familiarity_est", 0.0),
        "stage": "done" if done else row.get("stage", ""),
    }
    if done:
        result["handoff_ready"] = "scenario1"
    return _oc.dumps(result)


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
