"""Scenario 3: enroll campaign targets by @-mention, gated on the controller.

Targets used to reach ``outreach/state.yaml`` only two ways: an operator editing the
file by hand, or ``bin/discover_outreach_targets.py --set`` from a shell. Both need
an ``open_id`` in hand, which is exactly what a person running the campaign does not
have — they know colleagues by name and face, and the id lives in the org directory.

@-mention closes that gap: the ``mentions:`` line of ``<feishu_context>`` carries the
real ``open_id`` of everyone the message @-ed, as a protocol fact with no API
round-trip and no name matching. The controller writes 「把 @张三 @李四 加进来」 and
this tool writes the rows.

**This tool is an authorization boundary, not a convenience.** Enrolling somebody
starts a daily DM campaign aimed at them, from a bot, without asking them — so the
caller must be ``controller_open_id``, and an unset controller refuses everyone (see
``_outreach_confirm.controller_open_id``). The gate is here rather than in the skill
because a prompt-level rule is advice, and this write is not reversible by the person
it affects.
"""

from __future__ import annotations

from typing import Any

import _outreach_confirm as _oc

# Ids are ``ou_...``; a ``chat_id`` (``oc_...``) or a name would each write a row that
# can never match a real DM sender, and the campaign would look silently broken.
_ID_PREFIX = "ou_"


async def outreach_target_add(
    open_ids: list[str] | None = None,
    caller_open_id: str = "",
    names: list[str] | None = None,
) -> str:
    """Enroll one or more @-mentioned people as agent-literacy campaign targets.

    Use this when the campaign controller asks you to add people to the outreach
    cohort and @-mentions them (「把 @张三 加进来」). Take the ids from the
    ``mentions:`` line of ``<feishu_context>`` — those are real ``open_id`` values.
    Never take them from the message text: the text shows display **names**, and two
    colleagues can share one.

    Only the campaign controller may enroll targets, since being enrolled means
    receiving a daily DM from the bot. Pass ``caller_open_id`` from
    ``sender_open_id``; a non-controller is refused with ``not_authorized``, and you
    should relay that refusal plainly rather than retrying.

    Drop the bot's own ``open_id`` if the controller @-ed the bot to address it — that
    is addressing, not a target. Enrolling somebody already in the cohort is safe: it
    reports ``already_a_target`` and keeps their existing progress untouched.

    A newly added target starts at ``qna_reactive`` and nothing is sent to them now.
    Scenario 3 activates the next time they ask about agents/LLMs/HaiTun **in their
    own DM with the bot**, and Scenario 1's daily push picks them up on its next run.
    Tell the controller that, so silence right after adding is not read as a failure.

    Args:
        open_ids: The ``open_id`` of each person to enroll, from ``mentions:``.
        caller_open_id: The requester's own ``open_id`` (``sender_open_id``). Required
            — the authorization check has nothing to compare against without it.
        names: Display names positionally matching ``open_ids`` (optional, from
            ``mentions:``). Only a label in the state file; the id is what identifies.
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
            "controller_open_id is unset in outreach/state.yaml, so nobody may enroll targets — "
            "an operator must set it first (it decides who can start a daily DM campaign against someone)",
        )
    if caller != controller:
        return _oc.error(
            "not_authorized",
            "only the campaign controller may enroll targets",
            caller_open_id=caller,
        )

    label = _labels(requested, names)
    added: list[dict[str, str]] = []
    already: list[str] = []
    rejected: list[dict[str, str]] = []

    for open_id in requested:
        if not open_id.startswith(_ID_PREFIX):
            rejected.append({"open_id": open_id, "reason": f"not an open_id (expected {_ID_PREFIX}...)"})
            continue
        # Written one row at a time, each with its own re-read: the alternative
        # (build the whole list, write once) would drop a concurrent Scenario 1
        # ``daily`` update, and a partial success here is still honest — the result
        # names exactly who got in.
        action, row = _oc.add_target(state_file, open_id, label.get(open_id, ""))
        if action == "added":
            added.append({"open_id": open_id, "name": str((row or {}).get("name") or "")})
        elif action == "already_a_target":
            already.append(open_id)
        else:
            rejected.append({"open_id": open_id, "reason": action})

    result: dict[str, Any] = {
        "ok": not rejected,
        "action": "targets_added" if added else "no_change",
        "added": added,
        "already_a_target": already,
        "total_targets": _target_count(state_file),
    }
    if rejected:
        result["rejected"] = rejected
    if added:
        result["next_step"] = (
            "Nothing was sent to them. Scenario 3 starts when they next ask about "
            "agents/LLMs/HaiTun in their own DM with the bot; Scenario 1 picks them up "
            "on its next daily run. Say this — silence now is expected, not a failure."
        )
    return _oc.dumps(result)


def _labels(open_ids: list[str], names: list[str] | None) -> dict[str, str]:
    """Zip ids to display names positionally, tolerating a short or absent list.

    The names are cosmetic, so a mismatched list must not cost the enrollment: any
    id without a name falls back to the id itself in ``fresh_user``.
    """
    cleaned = [str(n or "").strip() for n in (names or [])]
    return {open_id: cleaned[i] for i, open_id in enumerate(open_ids) if i < len(cleaned) and cleaned[i]}


def _target_count(state_file: Any) -> int:
    """Cohort size after the writes — re-read, so it reflects what is on disk."""
    state = _oc.read_yaml_mapping(state_file)
    users = (state or {}).get("users")
    return len(users) if isinstance(users, list) else 0
