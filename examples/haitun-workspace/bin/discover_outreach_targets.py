"""Discover real ``open_id`` values for the outreach campaign and write them into
``outreach/state.yaml``.

The campaign cannot send anything while ``users[].open_id`` holds the
``ou_REPLACE_ME_*`` placeholders — Feishu rejects an invalid ``receive_id``. This
script fills them in from the org directory.

Credentials are read from the environment only; nothing is written to the repo:

    export PSI_FEISHU_APP_ID=cli_...
    export PSI_FEISHU_APP_SECRET=...

Usage (from the repo root):

    # 1. Verify credentials and list candidates, changing nothing:
    uv run python examples/haitun-workspace/bin/discover_outreach_targets.py --list

    # 2. Write chosen targets into state.yaml:
    uv run python examples/haitun-workspace/bin/discover_outreach_targets.py \
        --set ou_abc123 ou_def456

``--list`` needs the app's contact visibility range (tongxunlu quanxian fanwei) to
cover the people you want to see, plus the ``contact:contact.base:readonly`` scope.
If it returns nothing, the scope or the visibility range is the cause — not this
script; use ``--set`` with ids you already know.
"""

from __future__ import annotations

# ruff: noqa: T201 — this is a CLI script; print is the output channel.
import argparse
import asyncio
import io
import os
import sys
from pathlib import Path

import yaml

# Windows consoles default to cp1252, which cannot encode the arrows/dashes used
# below (argparse writes --help straight to stdout and would raise).
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
STATE_PATH = WORKSPACE / "outreach" / "state.yaml"
PLACEHOLDER_PREFIX = "ou_REPLACE_ME"


def _require_credentials() -> None:
    missing = [k for k in ("PSI_FEISHU_APP_ID", "PSI_FEISHU_APP_SECRET") if not os.environ.get(k)]
    if missing:
        sys.exit(f"[error] Set {' and '.join(missing)} in the environment first.")


async def _list_candidates(recursive: bool) -> list[dict[str, str]]:
    """Members of the org root, as ``{open_id, name}`` — the pool to pick targets from."""
    # The workspace tools are only importable once tools/ is on the path, so this
    # import is deliberately deferred. Import _feishu_impl rather than the
    # per-domain module: it owns the shared client/token layer and re-exports it.
    sys.path.insert(0, str(WORKSPACE / "tools"))
    os.environ.setdefault("WORKSPACE_DIR", str(WORKSPACE))
    from _feishu_impl import list_department_members_impl  # ty: ignore  # noqa: PLC0415

    result = await list_department_members_impl("0", "open_department_id", "open_id", recursive)
    if not isinstance(result, dict) or not result.get("members"):
        detail = result.get("message") or result if isinstance(result, dict) else result
        print(f"[warn] no members returned — check scopes / visibility range.\n  {detail}")
        return []
    return [
        {"open_id": m["open_id"], "name": str(m.get("name") or "")}
        for m in result["members"]
        if isinstance(m, dict) and isinstance(m.get("open_id"), str)
    ]


def _load_state() -> dict:
    if not STATE_PATH.exists():
        sys.exit(f"[error] {STATE_PATH} not found. Copy state.example.yaml first.")
    return yaml.safe_load(STATE_PATH.read_text(encoding="utf-8")) or {}


def _fresh_user(open_id: str, name: str) -> dict:
    """A new target row, from the campaign's own seed definition.

    Deliberately delegated rather than spelled out here: ``outreach_target_add``
    enrolls targets too, and two hand-written field lists that must stay identical
    drift the moment one side gains a counter. The tools dir has to be importable
    for this, same as in ``_list_candidates``.
    """
    sys.path.insert(0, str(WORKSPACE / "tools"))
    import _outreach_confirm as oc  # ty: ignore  # noqa: PLC0415

    return oc.fresh_user(open_id, name)


def _set_targets(open_ids: list[str], names: dict[str, str]) -> None:
    """Replace ``users`` with the given ids, preserving per-user progress if the id stays.

    An id already in the campaign keeps its **whole** row — Scenario 3 progress
    (``stage``, ``last_qa``, ``answers``, the counters) included. Rebuilding the row
    from a fixed field list instead would silently reset a user's card history on
    every re-run.
    """
    state = _load_state()
    previous = {
        u["open_id"]: u for u in state.get("users") or [] if isinstance(u, dict) and isinstance(u.get("open_id"), str)
    }
    users = []
    for index, open_id in enumerate(open_ids, start=1):
        kept = previous.get(open_id)
        if kept is not None:
            # Keep every existing field; only refresh the display name if we resolved one.
            user = dict(kept)
            user["name"] = names.get(open_id) or kept.get("name") or f"Target {index}"
            users.append(user)
            continue
        users.append(_fresh_user(open_id, names.get(open_id) or f"Target {index}"))
    state["users"] = users
    STATE_PATH.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[ok] wrote {len(users)} target(s) to {STATE_PATH}")
    for u in users:
        kept_note = " (progress kept)" if u["open_id"] in previous else " (new)"
        print(f"       {u['open_id']}  {u['name']}{kept_note}")
    print("[note] comments in state.yaml are dropped by yaml.safe_dump — see outreach/README.md")


def _report_placeholders() -> None:
    state = _load_state()
    left = [
        u.get("open_id")
        for u in state.get("users") or []
        if isinstance(u, dict) and str(u.get("open_id", "")).startswith(PLACEHOLDER_PREFIX)
    ]
    if left:
        print(f"[warn] {len(left)} placeholder id(s) still present: {left}")
    else:
        print("[ok] no placeholder ids remain — the campaign can send.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="list candidate open_ids, change nothing")
    group.add_argument("--set", nargs="+", metavar="OPEN_ID", help="write these open_ids into state.yaml")
    group.add_argument("--check", action="store_true", help="report whether placeholders remain")
    parser.add_argument("--recursive", action="store_true", help="with --list, include sub-departments")
    args = parser.parse_args()

    if args.check:
        _report_placeholders()
        return

    _require_credentials()

    if args.list:
        for candidate in await _list_candidates(args.recursive):
            print(f"{candidate['open_id']}\t{candidate['name']}")
        return

    bad = [i for i in args.set if not i.startswith("ou_") or i.startswith(PLACEHOLDER_PREFIX)]
    if bad:
        sys.exit(f"[error] not usable open_ids: {bad} (expected real 'ou_...' values)")
    names = {c["open_id"]: c["name"] for c in await _list_candidates(recursive=True)}
    _set_targets(args.set, names)


if __name__ == "__main__":
    asyncio.run(main())

