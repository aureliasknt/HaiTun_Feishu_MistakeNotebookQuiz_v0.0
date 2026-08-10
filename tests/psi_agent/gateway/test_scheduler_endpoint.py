from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from psi_agent.gateway.server import _ensure_scheduler


class _SessionManager:
    def get_workspace(self, session_id: str) -> str:
        if session_id == "missing":
            raise LookupError("unknown session")
        return "D:/workspace"

    def get_backend_id(self, session_id: str) -> str:
        return "ai-1"

    def get_agent(self, session_id: str) -> str:
        return "D:/agent"


class _SchedulerManager:
    calls: list[tuple[str, str, str]]

    def __init__(self) -> None:
        self.calls = []

    async def ensure(self, workspace: str, *, ai_id: str, agent: str) -> str:
        self.calls.append((workspace, ai_id, agent))
        return "scheduler-1"


def _request(body: Any, schedm: _SchedulerManager) -> Any:
    async def read_json() -> Any:
        return body

    return SimpleNamespace(app={"sm": _SessionManager(), "schedm": schedm}, json=read_json)


@pytest.mark.anyio
async def test_ensure_scheduler_uses_session_routing_coordinates() -> None:
    schedm = _SchedulerManager()

    response = await _ensure_scheduler(_request({"session_id": "user-1"}, schedm))

    assert response.status == 200
    assert response.text is not None
    assert json.loads(response.text)["scheduler_id"] == "scheduler-1"
    assert schedm.calls == [("D:/workspace", "ai-1", "D:/agent")]


@pytest.mark.anyio
async def test_ensure_scheduler_rejects_unknown_session() -> None:
    response = await _ensure_scheduler(_request({"session_id": "missing"}, _SchedulerManager()))

    assert response.status == 404


@pytest.mark.anyio
async def test_ensure_scheduler_requires_session_id() -> None:
    response = await _ensure_scheduler(_request({}, _SchedulerManager()))

    assert response.status == 400
