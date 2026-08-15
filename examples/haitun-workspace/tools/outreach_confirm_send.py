"""Scenario 3 path A: answer a keyword question from the static bank + confirm card.

Fired by TRIGGER ``outreach-confirm-auto`` with ``fire=tool``, so no LLM sits on
the path the user waits on — detection to card is a few file reads and two Feishu
calls. A keyword with no bank entry is reported as ``bank_miss`` and nothing is
sent: the background LLM turn then answers it as usual (path B).
"""

from __future__ import annotations

import json
from typing import Any

import _outreach_confirm as _oc
from _feishu_impl import send_card_impl as _send_card_impl
from _feishu_impl import send_message_impl as _send_message_impl


async def outreach_confirm_send(event_payload_json: str = "{}") -> str:
    """Internal trigger handler: answer an agent-literacy question and ask for confirmation.

    Invoked by the ``feishu.agent_literacy.question`` event with ``fire=tool``.
    Normal conversations must not call it — in a chat turn, answer the question
    yourself and send the card as described in the ``outreach-confirmation-card``
    skill (path B).

    Sends two messages to the asker: the bank answer as text, then a single-use
    confirmation card whose three buttons dispatch to ``outreach_confirm``. The
    card's ``business_context`` carries the ``qa_id``, so the callback needs no
    memory of this turn. Finally ``last_qa`` is written to the user's row, which
    is also what tells the background LLM turn to stay silent.

    Args:
        event_payload_json: Event payload injected by the trigger runtime
            (``open_id``, ``text``, ``keyword``, ``message_id``, ``chat_id``).
    """
    try:
        payload = json.loads(event_payload_json)
    except ValueError:
        return _oc.error("invalid_argument", "event_payload_json must be a JSON object string")
    if not isinstance(payload, dict):
        return _oc.error("invalid_argument", "event_payload_json must be a JSON object")

    open_id = str(payload.get("open_id") or "").strip()
    question = str(payload.get("text") or "").strip()
    keyword = str(payload.get("keyword") or "").strip()
    if not open_id or not question:
        return _oc.error("invalid_argument", "event payload needs both open_id and text")

    state_file = _oc.state_path()
    state = _oc.read_yaml_mapping(state_file)
    if state is None:
        return _oc.error("state_unavailable", f"campaign state not readable at {state_file}")
    scenario = _oc.scenario_config(state)
    if scenario.get("enabled") is False:
        return _oc.dumps({"ok": True, "action": "disabled"})

    user = _oc.find_user(state, open_id)
    if user is None:
        # Not in the cohort: leave the reply to the ordinary LLM turn.
        return _oc.dumps({"ok": True, "action": "not_a_target", "open_id": open_id})

    bank = _oc.read_yaml_mapping(_oc.bank_path(state, state_file))
    resolved = _oc.resolve_entry(bank, keyword) if bank is not None else None
    if resolved is None:
        # Path B: the LLM turn answers and sends the card itself.
        return _oc.dumps({"ok": True, "action": "bank_miss", "keyword": keyword})
    canonical, entry = resolved
    # `topic` is the wiki slug, so it can be written into `node`; the canonical bank
    # key is only a lookup name and is the fallback when an entry omits the slug.
    topic = str(entry.get("topic") or "").strip() or canonical

    answer = str(entry.get("answer") or "").strip()
    if not answer:
        return _oc.dumps({"ok": True, "action": "bank_miss", "keyword": keyword, "reason": "entry has no answer"})
    summary = str(entry.get("summary") or "").strip() or answer

    qa_id = _oc.qa_id_for(open_id, question)
    probe = _probe_for(user, scenario, entry)
    sent = await _send_message_impl(open_id, answer, "open_id")
    if sent.get("ok") is False:
        return _oc.dumps({**sent, "action": "answer_send_failed", "keyword": keyword})
    card = await _send_card_impl(
        open_id,
        _oc.build_card(question, summary, qa_id, probe),
        "open_id",
        None,
        _oc.business_context(open_id, qa_id, keyword, topic, summary),
        _oc.action_handlers(),
    )
    if card.get("ok") is False:
        # The answer did land, so report the partial failure without re-sending it.
        return _oc.dumps({**card, "action": "card_send_failed", "answer_sent": True, "qa_id": qa_id})

    def _mutate(row: dict[str, Any]) -> None:
        row["last_qa"] = {
            "qa_id": qa_id,
            "question": question[:200],
            "keyword": keyword,
            "topic": topic,
            "card_message_id": str(card.get("message_id") or ""),
            "sent_at": _oc.now_iso(),
        }
        row["card_sent_count"] = int(row.get("card_sent_count") or 0) + 1

    row, reason = _oc.update_user(state_file, open_id, _mutate)
    return _oc.dumps(
        {
            "ok": True,
            "action": "answered",
            "qa_id": qa_id,
            "topic": topic,
            "keyword": keyword,
            "card_message_id": str(card.get("message_id") or ""),
            "state_written": row is not None,
            **({"state_warning": reason} if reason else {}),
        }
    )


def _probe_for(user: dict[str, Any], scenario: dict[str, Any], entry: dict[str, Any]) -> str:
    """Every Nth card carries a real question, so "understood" is not just a claim."""
    card_config = scenario.get("card")
    card_config = card_config if isinstance(card_config, dict) else {}
    try:
        every = int(card_config.get("probe_question_every") or 0)
    except TypeError, ValueError:
        return ""
    if every <= 0:
        return ""
    try:
        already_sent = int(user.get("card_sent_count") or 0)
    except TypeError, ValueError:
        already_sent = 0
    if (already_sent + 1) % every != 0:
        return ""
    return str(entry.get("probe_question") or "").strip()
