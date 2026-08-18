from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from psi_agent.gateway import _feishu_webapp as fw
from psi_agent.gateway._feishu_manager import is_web_session_id
from psi_agent.gateway.server import _create_feishu_app_session, _session_ai_socket

_UNSET = object()


class FakeAIManager:
    def __init__(self, sockets: dict[str, str]) -> None:
        self.sockets = sockets

    def get_socket(self, ai_id: str) -> str:
        return self.sockets[ai_id]


@dataclass(frozen=True)
class FakeSession:
    id: str
    backend_type: str
    backend_id: str


class FakeSessionManager:
    async def list_all(self) -> list[FakeSession]:
        return [FakeSession("session-1", "router", "router-1")]


@dataclass(frozen=True)
class FakeRouter:
    mode: str
    router_ai_id: str | None


class FakeRouterManager:
    def __init__(self, mode: str = "aggregation") -> None:
        self.mode = mode

    def get(self, router_id: str) -> FakeRouter:
        assert router_id == "router-1"
        return FakeRouter(
            mode=self.mode,
            router_ai_id=None if self.mode == "fallback" else "aggregator",
        )

    def get_socket(self, router_id: str) -> str:
        assert router_id == "router-1"
        return "fallback-public.sock"


@pytest.mark.anyio
async def test_title_socket_for_router_backend_uses_router_ai_id() -> None:
    app = web.Application()
    app["aim"] = FakeAIManager({"aggregator": "aggregate.sock", "upstream": "upstream.sock"})
    app["sm"] = FakeSessionManager()
    app["rm"] = FakeRouterManager()
    request = make_mocked_request("POST", "/titles/generate", app=app)

    assert await _session_ai_socket(request, "session-1") == "aggregate.sock"


@pytest.mark.anyio
async def test_title_socket_for_fallback_backend_uses_public_router_socket() -> None:
    app = web.Application()
    app["aim"] = FakeAIManager({"aggregator": "aggregate.sock"})
    app["sm"] = FakeSessionManager()
    app["rm"] = FakeRouterManager(mode="fallback")
    request = make_mocked_request("POST", "/titles/generate", app=app)

    assert await _session_ai_socket(request, "session-1") == "fallback-public.sock"


# ---------------------------------------------------------------------------
# POST /feishu/app/sessions —— 工作台里「新建任务」
#
# 最要紧的一条是 ``…_ignores_a_workspace_from_the_body``: 这个接口存在的**全部**理由,
# 就是 workspace 只能由 cookie 身份推出, 不能由浏览器声称。
# ---------------------------------------------------------------------------


class _FakeFeishuRouter:
    """按 open_id 幂等发 (socket, session_id) —— 与 ``FeishuManager.route`` 同一契约。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def route(self, open_id: str, **_: object) -> tuple[str, str]:
        self.calls.append(open_id)
        return f"socket-feishu-{open_id}", f"feishu-{open_id}"


@dataclass
class _CreatedSession:
    id: str
    backend_type: str
    backend_id: str
    workspace: str
    channel_socket: str
    agent: str = ""
    active_schedules: tuple[str, ...] = ()
    deactive_schedules: tuple[str, ...] = ()

    @property
    def scheduler(self) -> bool:
        return False


class _RecordingSessionManager:
    """记录 ``create`` 的入参 —— 断言 workspace 究竟来自哪里。"""

    def __init__(self, workspaces: dict[str, str] | None = None) -> None:
        self._workspaces = workspaces or {}
        self.created: list[dict[str, object]] = []

    def get_workspace(self, session_id: str) -> str:
        return self._workspaces.get(session_id, f"/ws/{session_id}")

    def get_agent(self, session_id: str) -> str:
        return "/agent/haitun"

    def get_backend_id(self, session_id: str) -> str:
        return "ai-bot"

    async def create(self, **kwargs: object) -> _CreatedSession:
        self.created.append(kwargs)
        return _CreatedSession(
            id=str(kwargs["id"]),
            backend_type=str(kwargs.get("backend_type") or "ai"),
            backend_id=str(kwargs.get("backend_id") or ""),
            workspace=str(kwargs.get("workspace") or ""),
            agent=str(kwargs.get("agent") or ""),
            channel_socket=f"socket-{kwargs['id']}",
        )


class _RecordingScheduler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def ensure(self, workspace: str, **_: object) -> None:
        self.calls.append(workspace)


async def _webapp_request(
    *,
    open_id: str,
    sm: object,
    fm: object | None = None,
    schedm: object | None = None,
    json_body: object = _UNSET,
) -> web.Request:
    """构造一个带 (或不带) 飞书身份 cookie 的请求。

    ``open_id`` 为空 = 未登录。非空时直接种一个已登录会话, 免去整套授权往返 —— 这里要测的
    是建会话, 不是登录。
    """
    auth = fw.FeishuWebAppAuth()
    app = web.Application()
    app["feishu_webapp"] = auth
    app["fm"] = fm if fm is not None else _FakeFeishuRouter()
    app["sm"] = sm
    app["schedm"] = schedm if schedm is not None else _RecordingScheduler()
    headers = {}
    if open_id:
        sid = await auth.open_session(open_id)
        headers["Cookie"] = f"{fw.COOKIE_NAME}={sid}"
    request = make_mocked_request("POST", "/feishu/app/sessions", app=app, headers=headers)
    if json_body is not _UNSET:

        async def _json(**_: object) -> object:
            return json_body

        request.json = _json  # type: ignore[method-assign]
    return request


def _body(resp: web.Response) -> dict[str, object]:
    assert resp.text is not None
    parsed = json.loads(resp.text)
    assert isinstance(parsed, dict)
    return parsed


@pytest.mark.anyio
async def test_feishu_app_session_lands_in_the_bots_workspace_with_its_own_id() -> None:
    """一个池子, 两条历史。

    workspace 与机器人**逐字相同** (用户画像 / llm_wiki / Supervisor / 交付物因此共享),
    而 session_id 不同 —— history 按 session_id 存, 所以两边对话天然不混。
    """
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    resp = await _create_feishu_app_session(await _webapp_request(open_id="ou_alice", sm=sm))

    assert resp.status == 201
    body = _body(resp)
    assert body["workspace"] == "/ws/alice"
    assert body["id"] != "feishu-ou_alice"
    assert is_web_session_id(str(body["id"]))


@pytest.mark.anyio
async def test_feishu_app_session_ignores_a_workspace_from_the_body() -> None:
    """这个接口存在的**全部**理由。

    ``POST /sessions`` 从 body 收 workspace 且不看身份; 若网页应用走那条路, 改一行 body 就能
    把 Session 建到别人的目录里。所以这里 body 说什么都不算。
    """
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    resp = await _create_feishu_app_session(
        await _webapp_request(
            open_id="ou_alice",
            sm=sm,
            json_body={"workspace": "/ws/victim", "id": "feishu-ou_victim"},
        )
    )

    assert resp.status == 201
    body = _body(resp)
    assert body["workspace"] == "/ws/alice"
    # id 也不许由 body 指定 —— 否则可以直接冒充成别人的机器人会话。
    assert body["id"] != "feishu-ou_victim"
    assert sm.created[0]["workspace"] == "/ws/alice"


@pytest.mark.anyio
async def test_feishu_app_session_without_an_identity_is_401() -> None:
    """没有身份就没有 workspace 可言 —— 不能退回任何缺省目录。"""
    sm = _RecordingSessionManager()
    resp = await _create_feishu_app_session(await _webapp_request(open_id="", sm=sm))

    assert resp.status == 401
    assert sm.created == []


@pytest.mark.anyio
async def test_feishu_app_session_inherits_ai_and_agent_from_the_bot_session() -> None:
    """页面没传模型时不该建出一个连不上上游的 Session。"""
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    resp = await _create_feishu_app_session(await _webapp_request(open_id="ou_alice", sm=sm))

    assert resp.status == 201
    body = _body(resp)
    assert body["backend_id"] == "ai-bot"
    assert body["agent"] == "/agent/haitun"


@pytest.mark.anyio
async def test_feishu_app_session_accepts_an_explicit_ai_id() -> None:
    """页面选了模型就用它 —— 只有 workspace 是不可协商的。"""
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    resp = await _create_feishu_app_session(
        await _webapp_request(open_id="ou_alice", sm=sm, json_body={"ai_id": "ai-picked"})
    )

    assert _body(resp)["backend_id"] == "ai-picked"


@pytest.mark.anyio
async def test_feishu_app_session_tolerates_an_empty_or_broken_body() -> None:
    """没有必填字段, 所以空 body / 非法 JSON 都该当「全用缺省」而不是 400。"""
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    resp = await _create_feishu_app_session(await _webapp_request(open_id="ou_alice", sm=sm))
    assert resp.status == 201

    # 非 dict 的 body 同样不该让人建不了任务。
    resp2 = await _create_feishu_app_session(
        await _webapp_request(open_id="ou_alice", sm=sm, json_body=["not", "a", "dict"])
    )
    assert resp2.status == 201


@pytest.mark.anyio
async def test_feishu_app_session_registers_the_scheduler_for_the_shared_workspace() -> None:
    """与 ``POST /sessions`` 一致: 该 workspace 的 schedule 归它专属的调度 Session。

    ``SchedulerManager.ensure`` 按 workspace 去重, 所以同一 workspace 上多开子会话
    不会把调度翻倍。
    """
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice"})
    schedm = _RecordingScheduler()
    await _create_feishu_app_session(await _webapp_request(open_id="ou_alice", sm=sm, schedm=schedm))

    assert schedm.calls == ["/ws/alice"]


@pytest.mark.anyio
async def test_feishu_app_sessions_are_distinct_across_users() -> None:
    """两个人各自建任务, 不能落到同一个 id 或同一个目录。"""
    sm = _RecordingSessionManager({"feishu-ou_alice": "/ws/alice", "feishu-ou_bob": "/ws/bob"})
    alice = _body(await _create_feishu_app_session(await _webapp_request(open_id="ou_alice", sm=sm)))
    bob = _body(await _create_feishu_app_session(await _webapp_request(open_id="ou_bob", sm=sm)))

    assert alice["id"] != bob["id"]
    assert (alice["workspace"], bob["workspace"]) == ("/ws/alice", "/ws/bob")
