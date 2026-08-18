"""Scenario 3: send the 理解确认卡 for the answer just given, and make it current.

The card that used to ride along with a static bank answer. The answer itself is
now written by the model, but the card must not be — hand-assembling it meant the
turn had to get the ``qa_id``, the three ``value.action`` strings, the
``business_context`` and the ``action_handlers`` map all right, in JSON, every
time; any one of them wrong produced a card whose clicks resolved to no handler,
which looks identical to a working card until someone presses a button.

So the card stays deterministic: this tool builds it from the same helpers the
callback validates against (``_oc.build_card`` / ``business_context`` /
``action_handlers``), sends it, and repoints ``last_qa`` at the new ``qa_id``.
The card is byte-identical to the one the removed fast path sent, so
``outreach_confirm_handle`` cannot tell the two apart.

Call it **after** the answer message, never before: the card asks about text the
user has already read.
"""

# The card text is Chinese, where fullwidth question marks are correct.
# ruff: noqa: RUF002

from __future__ import annotations

from typing import Any

import _outreach_confirm as _oc
from _feishu_impl import send_card_impl as _send_card_impl


async def outreach_confirm_card(
    open_id: str, topic: str = "", keyword: str = "", summary: str = "", question: str = ""
) -> str:
    """Send the understanding-confirmation card for the answer you just sent.

    Use this in the agent-literacy campaign (Scenario 3) right after answering a
    target user's question about agents/LLMs/HaiTun, and again after re-explaining
    a point on a card callback. Do not write the card JSON yourself.

    The card is one line (「这次讲清楚了吗？」) and three buttons — ✅ 懂了 /
    🤔 不太懂 / ❌ 没看懂 — and carries no copy of the answer: it is sent directly
    after the message it asks about, so repeating that text would only push the
    buttons down the screen. Sending it makes it the user's current card: the
    previous one stops being answerable, which is what keeps one click tied to one
    exchange.

    Finish the turn with no further text after this returns — the card is the last
    thing the user should see. Reply only if this reports ``ok: false``.

    Args:
        open_id: The asker's ``open_id`` (a DM recipient, never a ``chat_id``).
        topic: Curriculum slug this exchange taught, e.g. ``what-is-an-agent``.
            Recorded as the user's current ``node``; falls back to ``keyword``.
        keyword: The campaign keyword the question hit, e.g. ``智能体``.
        summary: One line naming what was explained, for the callback's context.
            Not shown on the card.
        question: What the user actually asked, in their own words. Pass it —
            ``answers[]`` records this against the self-assessment, and it is the
            only evidence of *what* was assessed. Omitted, it falls back to
            ``summary``: still this exchange, just in your words rather than
            theirs. On a re-explanation card, keep the original question.
    """
    open_id = str(open_id or "").strip()
    if not open_id:
        return _oc.error("invalid_argument", "open_id is required (the asker's open_id, not a chat_id)")
    topic = str(topic or "").strip()
    keyword = str(keyword or "").strip()
    summary = str(summary or "").strip()
    question = str(question or "").strip()

    state_file = _oc.state_path()
    state = _oc.read_yaml_mapping(state_file)
    if state is None:
        return _oc.error("state_unavailable", f"campaign state not readable at {state_file}")
    scenario = _oc.scenario_config(state)
    if scenario.get("enabled") is False:
        return _oc.dumps({"ok": True, "action": "disabled"})
    user = _oc.find_user(state, open_id)
    if user is None:
        # Outside the cohort: answer the question normally, but write no state and
        # send no card — the campaign's counters describe its targets only.
        return _oc.dumps({"ok": True, "action": "not_a_target", "open_id": open_id})

    # Derived from the summary so two cards in one exchange cannot collide on it.
    qa_id = _oc.qa_id_for(open_id, summary or topic or keyword)
    node = topic or keyword
    card = await _send_card_impl(
        open_id,
        _oc.build_card(qa_id),
        "open_id",
        None,
        _oc.business_context(open_id, qa_id, keyword, node, summary),
        _oc.action_handlers(),
    )
    if card.get("ok") is False:
        # The answer is already in the chat; report the failure rather than
        # pointing ``last_qa`` at a card that was never delivered.
        return _oc.dumps({**card, "action": "card_send_failed", "qa_id": qa_id})

    def _mutate(row: dict[str, Any]) -> None:
        # ``question`` must describe *this* exchange. Carrying the previous row's
        # value forward was wrong: after 17 cards the field still held the question
        # from an earlier one, so ``answers[]`` filed each self-assessment against
        # whatever had been asked before it. Prefer the caller's text, then this
        # exchange's summary; only reuse the old question when neither was given
        # (a re-explanation card, which is still about the original question).
        previous = row.get("last_qa")
        previous = previous if isinstance(previous, dict) else {}
        recorded = question or summary or str(previous.get("question") or "")
        row["last_qa"] = {
            "qa_id": qa_id,
            "question": recorded[:200],
            "keyword": keyword,
            "topic": node,
            "summary": summary[:200],
            "card_message_id": str(card.get("message_id") or ""),
            "sent_at": _oc.now_iso(),
        }
        row["card_sent_count"] = int(row.get("card_sent_count") or 0) + 1
        if node:
            row["node"] = node

    row, reason = _oc.update_user(state_file, open_id, _mutate)
    return _oc.dumps(
        {
            "ok": True,
            "action": "card_sent",
            "qa_id": qa_id,
            "topic": node,
            "keyword": keyword,
            "card_message_id": str(card.get("message_id") or ""),
            "state_written": row is not None,
            **({"state_warning": reason} if reason else {}),
        }
    )
