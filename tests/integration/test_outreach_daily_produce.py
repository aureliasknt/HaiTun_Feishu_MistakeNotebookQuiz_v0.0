"""Tests for the ``haitun.outreach.daily`` synthetic producer's cadence.

Covers the two things that were wrong or missing: ``poll_every_minutes`` was
documented but never read (poll stayed pinned at 5 min), and there was no way to
run a bounded fast cadence for testing without the daily-random rewrite
stomping it.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import anyio
import pytest
import yaml

_PRODUCE = (
    Path(__file__).parents[2]
    / "examples"
    / "haitun-workspace"
    / "channel_events"
    / "feishu"
    / "outreach_daily"
    / "produce.py"
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("outreach_produce", _PRODUCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_poll_every_minutes_is_honoured() -> None:
    assert mod._poll_seconds({"poll_every_minutes": 1}) == 60
    assert mod._poll_seconds({"poll_every_minutes": 0.5}) == 30


@pytest.mark.parametrize("value", [None, 0, -3, "abc", {}])
def test_poll_falls_back_to_default_on_bad_values(value: Any) -> None:
    assert mod._poll_seconds({"poll_every_minutes": value}) == mod._DEFAULT_POLL_SECONDS


def test_interval_step_only_active_for_positive_minutes() -> None:
    assert mod._interval_step({"interval_minutes": 10}) == timedelta(minutes=10)
    assert mod._interval_step({}) is None
    assert mod._interval_step({"interval_minutes": 0}) is None
    assert mod._interval_step({"interval_minutes": "nope"}) is None


def test_next_grid_slot_skips_missed_slots_without_looping() -> None:
    """A producer asleep past several slots must jump to the next future one."""
    base = datetime(2026, 8, 11, 19, 30, tzinfo=UTC)
    step = timedelta(minutes=10)
    # 35 minutes late: 19:30 fired, so 19:40/19:50/20:00 are gone → 20:10.
    now = base + timedelta(minutes=35)
    assert mod._next_grid_slot(base, step, now) == datetime(2026, 8, 11, 20, 10, tzinfo=UTC)
    # Exactly on a slot boundary still advances (strictly future).
    assert mod._next_grid_slot(base, step, base) == base + step


class _Ctx:
    def __init__(self) -> None:
        self.emitted: list[dict[str, Any]] = []

    async def emit(self, envelope: dict[str, Any]) -> None:
        self.emitted.append(envelope)


async def _run_one_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: dict[str, Any]
) -> tuple[_Ctx, dict[str, Any]]:
    """Drive ``produce`` past one emit, then cancel it and read the state back.

    Cancellation rather than a patched ``anyio.sleep``: the producer shares that
    module with the test runner's own event loop. A second pass cannot double
    emit — by then ``next_send_at`` is in the future (or ``sending`` is held).
    """
    path = tmp_path / "state.yaml"
    path.write_text(yaml.safe_dump(state, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(path))

    ctx = _Ctx()
    with anyio.move_on_after(2):
        await mod.produce(ctx)
    return ctx, yaml.safe_load(path.read_text(encoding="utf-8"))


def _due_state(**daily: Any) -> dict[str, Any]:
    """State whose send is already due, polling fast enough to finish in-test."""
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    base = {"next_send_at": past, "sending": False, "poll_every_minutes": 0.001}
    return {"users": [{"open_id": "ou_a"}, {"open_id": "ou_b"}], "daily": base | daily}


async def test_interval_mode_advances_schedule_and_releases_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The producer owns the ladder in test mode, so an agent failure can't stall it."""
    until = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    ctx, after = await _run_one_iteration(tmp_path, monkeypatch, _due_state(interval_minutes=10, interval_until=until))
    assert len(ctx.emitted) == 1
    assert ctx.emitted[0]["payload"]["open_ids"] == ["ou_a", "ou_b"]
    assert after["daily"]["sending"] is False
    advanced = datetime.fromisoformat(after["daily"]["next_send_at"])
    assert advanced > datetime.now(UTC)
    assert after["daily"]["interval_minutes"] == 10


async def test_interval_window_expiry_reverts_to_daily_random(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Past interval_until the test fields are dropped, not left firing forever."""
    until = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    _, after = await _run_one_iteration(tmp_path, monkeypatch, _due_state(interval_minutes=10, interval_until=until))
    daily = after["daily"]
    assert "interval_minutes" not in daily
    assert "interval_until" not in daily
    assert datetime.fromisoformat(daily["next_send_at"]) > datetime.now(UTC)
    assert daily["sending"] is False


async def test_without_interval_mode_the_agent_still_owns_the_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Normal cadence: producer only sets the guard; it must not rewrite next_send_at."""
    state = _due_state()
    original = state["daily"]["next_send_at"]
    ctx, after = await _run_one_iteration(tmp_path, monkeypatch, state)
    assert len(ctx.emitted) == 1
    assert after["daily"]["next_send_at"] == original
    assert after["daily"]["sending"] is True


def test_next_daily_random_lands_tomorrow_inside_window() -> None:
    now = datetime(2026, 8, 11, 19, 18, tzinfo=UTC).astimezone(mod._TZ)
    daily = {"send_window": {"start": "09:00", "end": "21:00"}}
    for _ in range(50):
        slot = mod._next_daily_random(now, daily)
        assert slot.date() == (now.astimezone(mod._TZ) + timedelta(days=1)).date()
        assert 9 * 60 <= slot.hour * 60 + slot.minute <= 21 * 60
        assert slot.minute % 5 == 0
