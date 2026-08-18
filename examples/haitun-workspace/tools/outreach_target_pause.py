"""Scenario 3 + 1: pause or resume a campaign target, keeping their progress.

Stopping one user used to mean deleting their row (``discover_outreach_targets.py
--set`` without them), and the row **is** the progress — ``answers[]``,
``card_sent_count``, ``confident_count``, ``familiarity_est``. So the only available
"stop" also threw away the learning history it took weeks of cards to build, and
there was no way back.

Pausing sets ``status: paused`` and touches nothing else. Both scenarios then skip
that person — Scenario 3 grounds no turn and sends no card (``campaign_turn``),
Scenario 1 leaves them out of the daily send list (the producer's ``open_ids``) —
while every counter stays exactly where it was. Resuming is the same call with
``paused=false``.

``status`` was previously written by the seed and read by **nothing at all**, so
setting it by hand silently did nothing. It is honored now; ``_outreach_confirm.is_paused``
owns the definition of what counts as paused.

Same authorization boundary as ``outreach_target_add``: only ``controller_open_id``
may do this. Pausing is the less dangerous direction, but *resuming* restarts daily
DMs at somebody, so both directions go through the same gate.
"""

from __future__ import annotations

from typing import Any

import _outreach_confirm as _oc

# What each outcome means for the caller, so the model does not have to guess from
# the verb whether anything was actually written.
_REPORTED = {
    "paused": "campaign paused — progress kept",
    "resumed": "campaign resumed",
    "already_paused": "was already paused; nothing written",
    "already_active": "was already active; nothing written",
}


async def outreach_target_pause(
    open_ids: list[str] | None = None,
    caller_open_id: str = "",
    paused: bool = True,
) -> str:
    """Pause (or resume) the agent-literacy campaign for specific target users.

    Use this when the controller wants to stop the campaign for somebody — 「先别再
    发给 @张三 了」 — or to start it again later (``paused=false``). Take the ids from
    the ``mentions:`` line of ``<feishu_context>``, never from the message text,
    which shows display names that two colleagues can share.

    Pausing keeps the user's row and **all** their progress: their answers, cards
    and familiarity estimate are untouched, so resuming continues where they left
    off. It stops both halves at once — no reactive answer grounding, no
    confirmation cards, and no daily push. Use this rather than removing a target,
    which deletes that history irreversibly.

    Only the campaign controller may call this: resuming restarts daily DMs at
    somebody. A non-controller gets ``not_authorized`` — relay it and stop.

    Nothing is sent to the user either way. They are not told they were paused, so
    do not imply to the controller that anyone was notified.

    Args:
        open_ids: The ``open_id`` of each person to pause or resume, from ``mentions:``.
        caller_open_id: The requester's own ``open_id`` (``sender_open_id``). Required.
        paused: True pauses (the default), False resumes.
    """
    requested = [str(i or "").strip() for i in (open_ids or [])]
    requested = [i for i in requested if i]
    if not requested:
        return _oc.error("invalid_argument", "open_ids is required (take them from the <feishu_context> mentions line)")

    caller = str(caller_open_id or "").strip()
    if not caller:
        return _oc.error("invalid_argument", "caller_open_id is required (pass sender_open_id from <feishu_context>)")

    state_file = _oc.state_path()
    state = _oc.read_yaml_mapping(state_file)
    if state is None:
        return _oc.error("state_unavailable", f"campaign state not readable at {state_file}")

    controller = _oc.controller_open_id(state)
    if not controller:
        return _oc.error(
            "not_configured",
            "controller_open_id is unset in outreach/state.yaml, so nobody may change who the campaign targets",
        )
    if caller != controller:
        return _oc.error(
            "not_authorized",
            "only the campaign controller may pause or resume targets",
            caller_open_id=caller,
        )

    changed: list[str] = []
    unchanged: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    for open_id in requested:
        # One row at a time, each with its own re-read: the Scenario 1 producer owns
        # the ``daily`` block in this same file, and a batched write would clobber it.
        action, _row = _oc.set_paused(state_file, open_id, paused)
        if action in ("paused", "resumed"):
            changed.append(open_id)
        elif action in ("already_paused", "already_active"):
            unchanged.append({"open_id": open_id, "reason": _REPORTED[action]})
        else:
            failed.append({"open_id": open_id, "reason": action})

    result: dict[str, Any] = {
        "ok": not failed,
        "action": "paused" if paused else "resumed",
        "changed": changed,
        "active_targets": len(_oc.active_open_ids(_oc.read_yaml_mapping(state_file) or {})),
    }
    if unchanged:
        result["unchanged"] = unchanged
    if failed:
        result["failed"] = failed
    if changed and paused:
        result["next_step"] = (
            "They keep their whole history and were not notified. Nothing more will reach "
            "them — no answers grounded in the campaign, no cards, no daily push — until "
            "they are resumed."
        )
    elif changed:
        result["next_step"] = (
            "Their progress resumed from where it was. Scenario 3 activates again the next "
            "time they ask about agents; Scenario 1 includes them in the next daily run."
        )
    return _oc.dumps(result)
