"""Synthetic producer: ``haitun.outreach.daily`` (Scenario 1 — daily random-time cadence).

Reads ``outreach/state.yaml`` (location: env ``OUTREACH_STATE_PATH``, falling back
to ``WORKSPACE_DIR/outreach/state.yaml``; not found → idle + log). Emits one
envelope when ``now >= daily.next_send_at`` and ``daily.sending == false``:

- sets ``daily.sending = true`` before emitting (at-most-once guard; Session also
  dedups via ``idempotency_key``),
- ``routing.open_id = controller_open_id`` (empty → session default),
- ``idempotency_key = haitun.outreach.daily:<next_send_at>``.

After a successful emit, the agent (TRIGGER ``fire=prompt``) sends the daily
message and rewrites the state (last_daily_at, a new next_send_at, sending=false).
Stale guard: ``sending == true`` for more than 26 hours → reset (the agent failed
after the emit). A failed emit → release ``sending`` and retry on the next poll.

Cadence:

- normal — ``daily.next_send_at`` is written by the agent (tomorrow, at a random
  time inside ``send_window``);
- test mode — ``daily.interval_minutes`` > 0 uses a fixed cadence until
  ``daily.interval_until``. In this mode the producer itself advances
  ``next_send_at`` to the next grid slot and releases ``sending`` after emitting,
  so the ladder does not stall if the agent fails. Past ``interval_until`` → both
  fields are dropped and the schedule reverts to the daily random cadence.

``daily.poll_every_minutes`` controls the poll interval (default 5 minutes); for a
tight test cadence, set it to 1.

Note: the state file is rewritten with ``yaml.safe_dump`` — comments in
state.yaml are not preserved (the documentation lives in outreach/README.md).
"""

from __future__ import annotations

import math
import os
import random
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anyio
import yaml
from loguru import logger

_DEFAULT_POLL_SECONDS = 5 * 60  # default; overridden by daily.poll_every_minutes
_SENDING_STALE = timedelta(hours=26)
# Asia/Shanghai as a fixed offset: China has had no DST since 1991, so UTC+8 is
# always correct — and this needs no tzdata package (absent on Windows).
_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def _poll_seconds(daily: dict[str, Any]) -> float:
    """``daily.poll_every_minutes`` → seconds; invalid/≤0 → default 5 minutes."""
    try:
        minutes = float(str(daily.get("poll_every_minutes")))
    except ValueError:
        return _DEFAULT_POLL_SECONDS
    return minutes * 60 if minutes > 0 else _DEFAULT_POLL_SECONDS


def _state_path() -> Path | None:
    raw = os.environ.get("OUTREACH_STATE_PATH", "").strip()
    if raw:
        return Path(raw)
    ws = os.environ.get("WORKSPACE_DIR", "").strip()
    if ws:
        return Path(ws) / "outreach" / "state.yaml"
    return None


async def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        raw = await anyio.Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning(f"outreach state read failed: {exc}")
        return None
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        logger.warning(f"outreach state yaml invalid: {exc}")
        return None
    return value if isinstance(value, dict) else None


async def _write_state(path: Path, state: dict[str, Any]) -> None:
    try:
        await anyio.Path(path).write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"outreach state write failed: {exc}")


def _parse_iso(text: str) -> datetime | None:
    try:
        value = datetime.fromisoformat(text)
    except TypeError, ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def _interval_step(daily: dict[str, Any]) -> timedelta | None:
    """Test mode: ``daily.interval_minutes`` > 0 → fixed cadence, not daily random."""
    try:
        minutes = float(str(daily.get("interval_minutes")))
    except ValueError:
        return None
    return timedelta(minutes=minutes) if minutes > 0 else None


def _next_grid_slot(base: datetime, step: timedelta, now: datetime) -> datetime:
    """Next slot on the ``base + n*step`` grid that is > ``now`` (no looping)."""
    elapsed = (now - base).total_seconds()
    n = max(0, math.floor(elapsed / step.total_seconds()) + 1)
    return base + step * n


def _next_daily_random(now: datetime, daily: dict[str, Any]) -> datetime:
    """Tomorrow, random time inside ``send_window`` (default 09:00-21:00), rounded to 5 min."""
    window = daily.get("send_window") or {}
    start = str(window.get("start") or "09:00")
    end = str(window.get("end") or "21:00")

    def _minutes(text: str, fallback: int) -> int:
        try:
            hh, mm = text.split(":")
            return int(hh) * 60 + int(mm)
        except AttributeError, TypeError, ValueError:
            return fallback

    lo, hi = _minutes(start, 9 * 60), _minutes(end, 21 * 60)
    if hi < lo:
        lo, hi = hi, lo
    pick = random.randint(lo // 5, hi // 5) * 5
    tomorrow = (now.astimezone(_TZ) + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, pick // 60, pick % 60, tzinfo=_TZ)


async def produce(ctx: Any) -> None:
    while True:
        try:
            path = _state_path()
            if path is None:
                logger.info("outreach: OUTREACH_STATE_PATH / WORKSPACE_DIR unset — idle")
                await anyio.sleep(_DEFAULT_POLL_SECONDS)
                continue
            state = await _read_state(path)
            if state is None:
                logger.info(f"outreach: state not found at {path} — idle")
                await anyio.sleep(_DEFAULT_POLL_SECONDS)
                continue

            daily = state.get("daily") or {}
            poll = _poll_seconds(daily)
            next_raw = daily.get("next_send_at") or ""
            target = _parse_iso(next_raw)
            now = datetime.now(UTC)

            if target is None:
                await anyio.sleep(poll)
                continue

            sending = bool(daily.get("sending"))
            sending_at = _parse_iso(daily.get("sending_at") or "")
            if sending and sending_at is not None and now - sending_at > _SENDING_STALE:
                logger.warning("outreach: stale sending=true (>26h) — reset")
                state.setdefault("daily", {})["sending"] = False
                await _write_state(path, state)
                sending = False

            if now < target:
                await anyio.sleep(poll)
                continue
            if sending:
                await anyio.sleep(poll)
                continue

            # set the guard before emitting
            state.setdefault("daily", {})["sending"] = True
            state["daily"]["sending_at"] = now.isoformat()
            await _write_state(path, state)

            open_ids = [
                u.get("open_id")
                for u in state.get("users") or []
                if isinstance(u, dict) and isinstance(u.get("open_id"), str)
            ]
            routing: dict[str, str] = {}
            controller = (state.get("controller_open_id") or "").strip()
            if controller:
                routing["open_id"] = controller
            try:
                await ctx.emit(
                    {
                        "payload": {
                            "next_send_at": next_raw,
                            "cohort": state.get("cohort", ""),
                            "open_ids": open_ids,
                        },
                        "routing": routing,
                        "idempotency_key": f"haitun.outreach.daily:{next_raw}",
                    }
                )
                logger.info(
                    f"outreach: emitted daily (next_send_at={next_raw}, "
                    f"targets={len(open_ids)}, routing={routing or 'default'})"
                )
                # Test mode (interval_minutes): the producer advances the schedule
                # and releases the guard, so the 10-minute ladder does not stall if
                # the agent fails. Outside this mode the agent (TRIGGER) owns it.
                step = _interval_step(daily)
                if step is not None:
                    until = _parse_iso(daily.get("interval_until") or "")
                    upcoming = _next_grid_slot(target, step, now)
                    fresh = await _read_state(path) or state
                    node = fresh.setdefault("daily", {})
                    if until is not None and upcoming >= until:
                        # test window finished → back to the daily random cadence
                        node.pop("interval_minutes", None)
                        node.pop("interval_until", None)
                        node["next_send_at"] = _next_daily_random(now, daily).isoformat()
                        logger.info("outreach: interval window done — back to daily random")
                    else:
                        node["next_send_at"] = upcoming.isoformat()
                    node["sending"] = False
                    await _write_state(path, fresh)
            except Exception as exc:
                logger.warning(f"outreach: emit failed — release sending: {exc!r}")
                state.setdefault("daily", {})["sending"] = False
                await _write_state(path, state)

            # wait for the next poll; do not emit twice within one minute
            await anyio.sleep(poll)
        except Exception as exc:
            logger.error(f"outreach produce loop crashed: {exc!r}")
            await anyio.sleep(_DEFAULT_POLL_SECONDS)
