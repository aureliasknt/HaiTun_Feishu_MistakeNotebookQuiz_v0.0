from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any

import pytest

from psi_agent.gateway.server import _configure_feishu_runtime


def _request(body: Any, *, remote: str) -> Any:
    async def read_json() -> Any:
        return body

    return SimpleNamespace(remote=remote, json=read_json)


@pytest.mark.anyio
async def test_runtime_config_sets_process_environment_from_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PSI_FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("PSI_FEISHU_APP_SECRET", raising=False)

    response = await _configure_feishu_runtime(
        _request({"app_id": "cli_test", "app_secret": "secret_test"}, remote="127.0.0.1")
    )

    assert response.status == 200
    assert json.loads(response.text or "") == {"ok": True}
    assert os.environ["PSI_FEISHU_APP_ID"] == "cli_test"
    assert os.environ["PSI_FEISHU_APP_SECRET"] == "secret_test"
    assert "secret_test" not in (response.text or "")


@pytest.mark.anyio
async def test_runtime_config_rejects_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PSI_FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("PSI_FEISHU_APP_SECRET", raising=False)

    response = await _configure_feishu_runtime(
        _request({"app_id": "cli_test", "app_secret": "secret_test"}, remote="192.0.2.1")
    )

    assert response.status == 403
    assert "PSI_FEISHU_APP_SECRET" not in os.environ
