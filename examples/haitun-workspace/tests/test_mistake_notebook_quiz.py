from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from psi_agent.session.tool_registry import ToolFunction

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = WORKSPACE_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

quiz: Any = importlib.import_module("mistake_notebook_quiz")


@pytest.fixture()
def workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def test_tool_metadata_is_loadable() -> None:
    meta = ToolFunction.from_callable(quiz.mistake_notebook_quiz_send_next)
    assert set(meta.parameters["properties"]) == {
        "receive_id",
        "app_token",
        "table_id",
        "recipient_name",
        "interval_minutes",
        "window_start",
        "window_end",
        "not_before",
        "reset",
    }
    assert set(meta.parameters["required"]) == {"receive_id", "app_token", "table_id"}


@pytest.mark.anyio
async def test_send_advances_question_only_after_success(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_contexts: list[dict[str, str]] = []

    async def fake_send_card(**kwargs: str) -> str:
        sent_contexts.append(json.loads(kwargs["business_context_json"]))
        return json.dumps(
            {"ok": True, "callback_context_saved": True, "message_id": f"om_{len(sent_contexts)}"}
        )

    monkeypatch.setattr(quiz, "feishu_message_send_card", fake_send_card)
    now = datetime(2026, 8, 6, 13, 14)
    monkeypatch.setattr(quiz, "_now_local", lambda: now)

    first = await quiz.mistake_notebook_quiz_send_next(
        "ou_user", "base", "table", recipient_name="测试用户", reset=True
    )
    now += timedelta(hours=1)
    second = await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table")

    assert json.loads(first)["question_id"] == "q1"
    assert json.loads(second)["question_id"] == "q2"
    assert [item["question_id"] for item in sent_contexts] == ["q1", "q2"]
    assert sent_contexts[0]["recipient_name"] == "测试用户"
    state = json.loads(
        (workspace / ".psi" / "mistake-notebook-quiz" / "ou_user.json").read_text(encoding="utf-8")
    )
    assert state["next_index"] == 2
    assert state["last_sent_at"] == "2026-08-06T14:14:00"


@pytest.mark.anyio
async def test_reset_starts_again_from_q1(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    question_ids: list[str] = []

    async def fake_send_card(**kwargs: str) -> str:
        question_ids.append(json.loads(kwargs["business_context_json"])["question_id"])
        return '{"ok":true,"callback_context_saved":true,"message_id":"om_1"}'

    monkeypatch.setattr(quiz, "feishu_message_send_card", fake_send_card)
    now = datetime(2026, 8, 6, 13, 14)
    monkeypatch.setattr(quiz, "_now_local", lambda: now)
    await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table")
    await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table", reset=True)

    assert question_ids == ["q1", "q1"]


@pytest.mark.anyio
async def test_interval_is_configurable(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    now = datetime(2026, 8, 6, 13, 14)

    async def fake_send_card(**kwargs: str) -> str:
        nonlocal calls
        calls += 1
        return '{"ok":true,"callback_context_saved":true,"message_id":"om_1"}'

    monkeypatch.setattr(quiz, "feishu_message_send_card", fake_send_card)
    monkeypatch.setattr(quiz, "_now_local", lambda: now)
    await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table", reset=True)
    now += timedelta(minutes=9)
    early = await quiz.mistake_notebook_quiz_send_next(
        "ou_user", "base", "table", interval_minutes=10
    )
    now += timedelta(minutes=1)
    on_time = await quiz.mistake_notebook_quiz_send_next(
        "ou_user", "base", "table", interval_minutes=10
    )

    assert json.loads(early)["reason"] == "interval"
    assert json.loads(on_time)["question_id"] == "q2"
    assert calls == 2


@pytest.mark.anyio
async def test_window_end_is_enforced(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quiz, "_now_local", lambda: datetime(2026, 8, 6, 22, 1))

    result = await quiz.mistake_notebook_quiz_send_next(
        "ou_user", "base", "table", interval_minutes=10
    )

    assert json.loads(result)["reason"] == "outside_window"


@pytest.mark.anyio
async def test_not_before_skips_without_sending_or_advancing(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def fake_send_card(**kwargs: str) -> str:
        nonlocal called
        called = True
        return '{"ok":true,"callback_context_saved":true,"message_id":"om_1"}'

    monkeypatch.setattr(quiz, "feishu_message_send_card", fake_send_card)
    future = (quiz._now_local() + timedelta(hours=1)).isoformat(timespec="minutes")

    result = await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table", not_before=future)

    assert json.loads(result)["skipped"] is True
    assert called is False
    assert not (workspace / ".psi" / "mistake-notebook-quiz" / "ou_user.json").exists()


@pytest.mark.anyio
async def test_failed_send_does_not_advance(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_send_card(**kwargs: str) -> str:
        return '{"ok":false,"error":{"message":"denied"}}'

    monkeypatch.setattr(quiz, "feishu_message_send_card", fake_send_card)

    with pytest.raises(RuntimeError, match="quiz card send failed"):
        await quiz.mistake_notebook_quiz_send_next("ou_user", "base", "table")

    assert not (workspace / ".psi" / "mistake-notebook-quiz" / "ou_user.json").exists()


@pytest.mark.anyio
async def test_rejects_non_open_id(workspace: Path) -> None:
    result = await quiz.mistake_notebook_quiz_send_next("张三", "base", "table")
    assert json.loads(result)["ok"] is False
