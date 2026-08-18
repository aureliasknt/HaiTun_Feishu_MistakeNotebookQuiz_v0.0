"""场景 3 网页应用入口: 读待确认卡 → 作答。

提问不在这里 —— 那条零大模型的确定性发卡链路已整体移除, ``POST /outreach/ask`` 随之下线
(见 ``test_only_the_card_routes_are_registered``)。所以最要紧的两条是:

* ``test_every_route_refuses_an_anonymous_caller`` —— 身份只认 cookie; 一旦能从
  query/body 取 ``open_id``, 任何人都能替别人作答。
* ``test_answer_refuses_a_stale_qa_id`` / ``..._is_single_use`` —— 那张卡是一次性的,
  过期页面或重复提交都不该改动计数。
"""

# 卡面措辞是中文, 全角问号在这里正是该用的那一个。
# ruff: noqa: RUF001

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from psi_agent.gateway import _feishu_webapp as fw
from psi_agent.gateway import _outreach_api as oa

OPEN_ID = "ou_demo"
WORKSPACE = Path(__file__).resolve().parents[3] / "examples" / "haitun-workspace"


class _FakeFeishuManager:
    async def route(self, open_id: str, **_: Any) -> tuple[str, str]:
        return "socket-x", f"feishu-{open_id}"


def _state(tmp_path: Path, *, last_qa: dict[str, Any] | None = None, keywords: list[str] | None = None) -> Path:
    """A minimal campaign state plus a one-entry bank, both under *tmp_path*."""
    bank = tmp_path / "qna_bank.yaml"
    bank.write_text(
        yaml.safe_dump(
            {"qa_bank": {"agent": {"answer": "Agent 是…", "summary": "简短摘要", "probe_question": "试着说说?"}}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    user: dict[str, Any] = {"open_id": OPEN_ID, "answers": []}
    if last_qa is not None:
        user["last_qa"] = last_qa
    state = tmp_path / "state.yaml"
    state.write_text(
        yaml.safe_dump(
            {
                "scenario3": {
                    "enabled": True,
                    "keywords": keywords if keywords is not None else ["agent"],
                    "qa_bank_path": str(bank),
                },
                "users": [user],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return state


_state_holder: dict[str, Path] = {}


@pytest.fixture
def oc(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Load the real workspace helpers, with ``state_path()`` redirected per test."""
    module = oa._load_workspace_module(str(WORKSPACE), "_outreach_confirm")
    monkeypatch.setattr(module, "state_path", lambda: _state_holder["path"])
    return module


def _request(
    method: str,
    path: str,
    *,
    auth: fw.FeishuWebAppAuth,
    cookies: dict[str, str] | None = None,
    fm: Any = None,
    body: dict[str, Any] | None = None,
) -> web.Request:
    app = web.Application()
    app["feishu_webapp"] = auth
    app["outreach_workspace_root"] = str(WORKSPACE)
    if fm is not None:
        app["fm"] = fm
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    request = make_mocked_request(method, path, app=app, headers=headers)
    if body is not None:
        payload = json.dumps(body).encode()

        async def _json(**_: Any) -> Any:
            return json.loads(payload)

        request.json = _json  # type: ignore[method-assign]
    return request


def _payload(resp: web.Response) -> dict[str, Any]:
    assert resp.text is not None
    parsed = json.loads(resp.text)
    assert isinstance(parsed, dict)
    return parsed


async def _logged_in(auth: fw.FeishuWebAppAuth) -> dict[str, str]:
    return {fw.COOKIE_NAME: await auth.open_session(OPEN_ID)}


@pytest.mark.anyio
async def test_every_route_refuses_an_anonymous_caller() -> None:
    """身份只能来自 cookie —— 否则任何人都能替别人作答。"""
    auth = fw.FeishuWebAppAuth()
    for method, path, body in (
        ("GET", "/outreach/card", None),
        ("POST", "/outreach/answer", {"qa_id": "x", "answer": "understood"}),
    ):
        handler = {
            "/outreach/card": oa.handle_card,
            "/outreach/answer": oa.handle_answer,
        }[path]
        resp = await handler(_request(method, path, auth=auth, body=body))
        assert resp.status == 401, f"{path} must be 401 without a cookie"


@pytest.mark.anyio
async def test_only_the_card_routes_are_registered() -> None:
    """提问入口已随确定性发卡链路一并移除 —— 别再挂回来。

    ``POST /outreach/ask`` 的存在意义只有一个: 造一个合成信封去命中那条 ``fire=tool``
    的 TRIGGER, 让工具在零大模型的前提下发出题库答案。答案现在由模型写, 而模型本来就在
    私聊那一轮里, 所以这个端点没有第二个用途, 留着只会是一条绕过技能的旁路。
    """
    app = web.Application()
    oa.register(app, workspace_root=str(WORKSPACE))
    paths = {route.resource.canonical for route in app.router.routes() if route.resource is not None}
    assert paths == {"/outreach/card", "/outreach/answer"}
    assert not hasattr(oa, "handle_ask")


@pytest.mark.anyio
async def test_card_reports_only_the_prompt_and_the_qa_id(tmp_path: Path, oc: Any) -> None:
    """卡面只有一句提问 + 三个按钮, 所以这里不再回查摘要与检验题 —— 答案(含检验题)由
    ``POST /outreach/ask`` 交给页面, 卡紧跟其后, 复述一遍只会让人读两遍。"""
    _state_holder["path"] = _state(tmp_path, last_qa={"qa_id": "qa1", "question": "什么是 agent?", "keyword": "agent"})
    auth = fw.FeishuWebAppAuth()
    resp = await oa.handle_card(_request("GET", "/outreach/card", auth=auth, cookies=await _logged_in(auth)))
    body = _payload(resp)
    assert body["available"] is True
    assert body["qa_id"] == "qa1"
    # 与飞书那张卡同一处措辞 (``_outreach_confirm.CARD_PROMPT``), 不各写一份。
    assert body["prompt"] == oc.CARD_PROMPT == "这次讲清楚了吗？"
    assert "summary" not in body and "probe" not in body and "question" not in body


@pytest.mark.anyio
async def test_card_is_absent_before_any_question_and_after_answering(tmp_path: Path, oc: Any) -> None:
    auth = fw.FeishuWebAppAuth()
    _state_holder["path"] = _state(tmp_path)
    fresh = await oa.handle_card(_request("GET", "/outreach/card", auth=auth, cookies=await _logged_in(auth)))
    assert _payload(fresh) == {"available": False}

    _state_holder["path"] = _state(
        tmp_path, last_qa={"qa_id": "qa1", "question": "q", "keyword": "agent", "answered_at": "2026-08-14T00:00:00Z"}
    )
    done = await oa.handle_card(_request("GET", "/outreach/card", auth=auth, cookies=await _logged_in(auth)))
    assert _payload(done)["available"] is False
    assert _payload(done)["reason"] == "already_answered"


@pytest.mark.anyio
async def test_answer_records_the_assessment_and_marks_the_card_used(tmp_path: Path, oc: Any) -> None:
    state_file = _state(tmp_path, last_qa={"qa_id": "qa1", "question": "什么是 agent?", "keyword": "agent"})
    _state_holder["path"] = state_file
    auth = fw.FeishuWebAppAuth()
    resp = await oa.handle_answer(
        _request(
            "POST",
            "/outreach/answer",
            auth=auth,
            cookies=await _logged_in(auth),
            body={"qa_id": "qa1", "answer": "understood"},
        )
    )
    assert resp.status == 200
    assert _payload(resp)["answer"] == "understood"

    row = yaml.safe_load(state_file.read_text(encoding="utf-8"))["users"][0]
    assert row["last_qa"]["answered_at"]
    assert row["last_qa"]["self_assessment"] == "understood"
    assert row["answers"][-1]["qa_id"] == "qa1"
    assert row["answers"][-1]["self_assessment"] == "understood"


@pytest.mark.anyio
async def test_answer_refuses_a_stale_qa_id_without_touching_counters(tmp_path: Path, oc: Any) -> None:
    """过期页面不能改动计数 —— 与 outreach_confirm_handle 的 qa_id 闸门同一语义。"""
    state_file = _state(tmp_path, last_qa={"qa_id": "qa-current", "question": "q", "keyword": "agent"})
    _state_holder["path"] = state_file
    auth = fw.FeishuWebAppAuth()
    resp = await oa.handle_answer(
        _request(
            "POST",
            "/outreach/answer",
            auth=auth,
            cookies=await _logged_in(auth),
            body={"qa_id": "qa-old", "answer": "understood"},
        )
    )
    assert resp.status == 409
    row = yaml.safe_load(state_file.read_text(encoding="utf-8"))["users"][0]
    assert row["answers"] == []
    assert "answered_at" not in row["last_qa"]


@pytest.mark.anyio
async def test_answer_is_single_use(tmp_path: Path, oc: Any) -> None:
    state_file = _state(tmp_path, last_qa={"qa_id": "qa1", "question": "q", "keyword": "agent"})
    _state_holder["path"] = state_file
    auth = fw.FeishuWebAppAuth()
    cookies = await _logged_in(auth)

    first = await oa.handle_answer(
        _request("POST", "/outreach/answer", auth=auth, cookies=cookies, body={"qa_id": "qa1", "answer": "partial"})
    )
    assert first.status == 200
    second = await oa.handle_answer(
        _request("POST", "/outreach/answer", auth=auth, cookies=cookies, body={"qa_id": "qa1", "answer": "understood"})
    )
    assert second.status == 409
    row = yaml.safe_load(state_file.read_text(encoding="utf-8"))["users"][0]
    assert len(row["answers"]) == 1, "a single-use card must not record two answers"


@pytest.mark.anyio
async def test_answer_rejects_an_unknown_assessment_value(tmp_path: Path, oc: Any) -> None:
    _state_holder["path"] = _state(tmp_path, last_qa={"qa_id": "qa1", "question": "q", "keyword": "agent"})
    auth = fw.FeishuWebAppAuth()
    resp = await oa.handle_answer(
        _request(
            "POST",
            "/outreach/answer",
            auth=auth,
            cookies=await _logged_in(auth),
            body={"qa_id": "qa1", "answer": "maybe"},
        )
    )
    assert resp.status == 400
