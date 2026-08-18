"""飞书网页应用身份层: cookie → open_id → 与机器人**同一个** Session。

最要紧的一条是 ``test_me_binds_the_same_session_the_bot_uses``: 工作台与机器人共享
用户画像 / llm_wiki / Supervisor 的**全部**依据, 就是两边落在同一个 Session 上。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from psi_agent.gateway import _feishu_webapp as fw

_UNSET = object()
# 让 ``request.json()`` 抛错, 模拟非法请求体。
_BAD_JSON = object()


class _FakeFeishuManager:
    """按 open_id 幂等地发 session_id —— 与真 ``FeishuManager.route`` 同一契约。"""

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self.calls: list[str] = []

    async def route(self, open_id: str, **_: Any) -> tuple[str, str]:
        self.calls.append(open_id)
        session_id = self._sessions.setdefault(open_id, f"sess-{len(self._sessions)}")
        return f"socket-{session_id}", session_id


class _FakeSessionManager:
    def __init__(self, workspaces: dict[str, str] | None = None) -> None:
        self._workspaces = workspaces or {}

    def get_workspace(self, session_id: str) -> str:
        return self._workspaces.get(session_id, f"/ws/{session_id}")


class _FakeTransport:
    """``request.remote`` 取自 ``transport.get_extra_info("peername")``。"""

    def __init__(self, host: str) -> None:
        self._host = host

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name == "peername":
            return (self._host, 54321)
        if name == "socket":
            return None
        return default

    def is_closing(self) -> bool:
        return False


def _request(
    method: str,
    path: str,
    *,
    auth: fw.FeishuWebAppAuth,
    fm: Any = None,
    sm: Any = None,
    cookies: dict[str, str] | None = None,
    remote: str = "127.0.0.1",
    user_agent: str = "",
    forwarded_proto: str = "",
    json_body: Any = _UNSET,
) -> web.Request:
    app = web.Application()
    app["feishu_webapp"] = auth
    if fm is not None:
        app["fm"] = fm
    if sm is not None:
        app["sm"] = sm
    headers = {}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if user_agent:
        headers["User-Agent"] = user_agent
    if forwarded_proto:
        # 工作台通常跑在反代之后, 所以「是不是 HTTPS」只能从这个头看出来。
        headers["X-Forwarded-Proto"] = forwarded_proto
    request = make_mocked_request(method, path, app=app, headers=headers, transport=_FakeTransport(remote))
    if json_body is not _UNSET:

        async def _json(**_: Any) -> Any:
            if json_body is _BAD_JSON:
                raise ValueError("not json")
            return json_body

        request.json = _json  # type: ignore[method-assign]
    return request


def _payload(resp: web.Response) -> dict[str, Any]:
    assert resp.text is not None
    parsed = json.loads(resp.text)
    assert isinstance(parsed, dict)
    return parsed


@pytest.mark.anyio
async def test_me_without_cookie_reports_unauthenticated_not_an_error() -> None:
    """SPA 启动时必然先无 cookie 地问一次; 那不是错误, 只是「桌面模式」。"""
    resp = await fw.handle_me(_request("GET", "/feishu/app/me", auth=fw.FeishuWebAppAuth()))
    assert resp.status == 200
    body = _payload(resp)
    assert body["authenticated"] is False
    assert body["configured"] is False


@pytest.mark.anyio
async def test_login_without_credentials_is_501_not_a_broken_redirect() -> None:
    resp = await fw.handle_login(_request("GET", "/feishu/app/login", auth=fw.FeishuWebAppAuth()))
    assert resp.status == 501


@pytest.mark.anyio
async def test_callback_with_unknown_state_is_rejected_before_any_network_call() -> None:
    """state 校验必须先于换取令牌 —— 否则就成了替别人换 code 的开放代理。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _boom(*_: Any, **__: Any) -> str:  # pragma: no cover - 不该被调用
        raise AssertionError("exchange_code must not run for an unknown state")

    auth.exchange_code = _boom  # type: ignore[method-assign]
    resp = await fw.handle_callback(_request("GET", "/feishu/app/callback?code=c&state=nope", auth=auth))
    assert resp.status == 400
    assert "state" in _payload(resp)["error"]


@pytest.mark.anyio
async def test_state_is_single_use() -> None:
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")
    state = await auth.issue_state()
    assert await auth.consume_state(state) is True
    assert await auth.consume_state(state) is False


@pytest.mark.anyio
async def test_me_binds_the_same_session_the_bot_uses(monkeypatch: pytest.MonkeyPatch) -> None:
    """工作台与机器人共享数据的**唯一**依据: 同一个 open_id → 同一个 session_id。"""
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    auth = fw.FeishuWebAppAuth()
    fm = _FakeFeishuManager()
    sm = _FakeSessionManager()

    # 机器人先来 (channel → POST /feishu/route)。
    _socket, bot_session = await fm.route("ou_demo")

    resp = await fw.handle_me(_request("GET", "/feishu/app/me", auth=auth, fm=fm, sm=sm))
    assert resp.status == 200
    body = _payload(resp)
    assert body["authenticated"] is True
    assert body["open_id"] == "ou_demo"
    assert body["session_id"] == bot_session
    assert body["workspace"] == f"/ws/{bot_session}"


@pytest.mark.anyio
async def test_mock_mode_is_refused_from_a_non_loopback_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    """否则 mock 模式就是一个「任填 open_id 冒充任何人」的入口。"""
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    resp = await fw.handle_me(
        _request("GET", "/feishu/app/me", auth=fw.FeishuWebAppAuth(), fm=_FakeFeishuManager(), remote="10.1.2.3")
    )
    assert resp.status == 403


@pytest.mark.anyio
async def test_cookie_identity_survives_and_is_httponly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    auth = fw.FeishuWebAppAuth()
    fm = _FakeFeishuManager()

    first = await fw.handle_me(_request("GET", "/feishu/app/me", auth=auth, fm=fm, sm=_FakeSessionManager()))
    cookie = first.cookies[fw.COOKIE_NAME]
    assert "httponly" in str(cookie).lower()

    # 第二次带 cookie 且关掉 mock: 身份仍在, 说明认的是 cookie 而不是 env。
    monkeypatch.delenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", raising=False)
    second = await fw.handle_me(
        _request(
            "GET",
            "/feishu/app/me",
            auth=auth,
            fm=fm,
            sm=_FakeSessionManager(),
            cookies={fw.COOKIE_NAME: cookie.value},
        )
    )
    assert _payload(second)["open_id"] == "ou_demo"


@pytest.mark.anyio
async def test_logout_drops_the_identity() -> None:
    auth = fw.FeishuWebAppAuth()
    sid = await auth.open_session("ou_demo")
    assert await auth.resolve(sid) == "ou_demo"

    resp = await fw.handle_logout(_request("POST", "/feishu/app/logout", auth=auth, cookies={fw.COOKIE_NAME: sid}))
    assert _payload(resp)["authenticated"] is False
    assert await auth.resolve(sid) == ""


@pytest.mark.anyio
async def test_app_secret_never_appears_in_a_response_body() -> None:
    """凭据只该在服务端与飞书之间流动, 绝不回显给浏览器。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="s3cr3t-value")
    resp = await fw.handle_me(_request("GET", "/feishu/app/me", auth=auth))
    assert "s3cr3t-value" not in (resp.text or "")

    denied = await fw.handle_callback(_request("GET", "/feishu/app/callback?code=c&state=bad", auth=auth))
    assert "s3cr3t-value" not in (denied.text or "")


@pytest.mark.anyio
async def test_me_without_feishu_routing_says_so_instead_of_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    resp = await fw.handle_me(_request("GET", "/feishu/app/me", auth=fw.FeishuWebAppAuth()))
    assert resp.status == 501


@pytest.mark.anyio
async def test_js_login_exchanges_the_code_and_pins_the_identity_without_a_redirect() -> None:
    """客户端内的首选路径: 免登码换 cookie, 没有整页跳转 (那在 webview 里既慢又易跑偏)。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _exchange(code: str) -> fw.FeishuUserInfo:
        assert code == "免登码-abc"
        return fw.FeishuUserInfo(open_id="ou_from_js", name="张三")

    auth.exchange_js_code = _exchange  # type: ignore[method-assign]
    resp = await fw.handle_js_login(
        _request("POST", "/feishu/app/js-login", auth=auth, json_body={"code": "免登码-abc"})
    )
    assert resp.status == 200
    # 302 会把用户从 SPA 里踢走 —— 免登的全部意义就是不发生这件事。
    assert isinstance(resp, web.Response)
    cookie = resp.cookies[fw.COOKIE_NAME]
    assert "httponly" in str(cookie).lower()
    assert await auth.resolve(cookie.value) == "ou_from_js"
    # 名字随身份一起钉住, 供后续 /feishu/app/me 播种 USER.md。
    stored = await auth.resolve_user(cookie.value)
    assert stored is not None
    assert stored.name == "张三"


@pytest.mark.anyio
async def test_js_login_does_not_echo_the_open_id_or_the_secret() -> None:
    """身份只由 ``/feishu/app/me`` 一处给出; 凭据一处都不给。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="s3cr3t-value")

    async def _exchange(*_: Any, **__: Any) -> fw.FeishuUserInfo:
        return fw.FeishuUserInfo(open_id="ou_from_js", name="张三")

    auth.exchange_js_code = _exchange  # type: ignore[method-assign]
    resp = await fw.handle_js_login(_request("POST", "/feishu/app/js-login", auth=auth, json_body={"code": "c"}))
    body = resp.text or ""
    assert "s3cr3t-value" not in body
    assert "ou_from_js" not in body


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"code": "  "}, _BAD_JSON, []])
async def test_js_login_rejects_a_request_without_a_usable_code(payload: Any) -> None:
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _boom(*_: Any, **__: Any) -> str:  # pragma: no cover - 不该被调用
        raise AssertionError("exchange_js_code must not run without a code")

    auth.exchange_js_code = _boom  # type: ignore[method-assign]
    resp = await fw.handle_js_login(_request("POST", "/feishu/app/js-login", auth=auth, json_body=payload))
    assert resp.status == 400


@pytest.mark.anyio
async def test_js_login_without_credentials_is_501_so_the_page_can_stay_in_desktop_mode() -> None:
    """501 与 ``/feishu/app/login`` 同义: 「这台 Gateway 没配网页应用」, 不是「码错了」。"""
    resp = await fw.handle_js_login(
        _request("POST", "/feishu/app/js-login", auth=fw.FeishuWebAppAuth(), json_body={"code": "c"})
    )
    assert resp.status == 501


@pytest.mark.anyio
async def test_js_login_maps_a_feishu_refusal_to_400_and_a_network_fault_to_502() -> None:
    """两者对页面的意思不同: 前者别再试, 后者重试或退回授权码回跳。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _refused(*_: Any, **__: Any) -> str:
        raise ValueError("免登码未换到 open_id: code=20037")

    auth.exchange_js_code = _refused  # type: ignore[method-assign]
    refused = await fw.handle_js_login(_request("POST", "/feishu/app/js-login", auth=auth, json_body={"code": "c"}))
    assert refused.status == 400

    async def _offline(*_: Any, **__: Any) -> str:
        raise TimeoutError

    auth.exchange_js_code = _offline  # type: ignore[method-assign]
    offline = await fw.handle_js_login(_request("POST", "/feishu/app/js-login", auth=auth, json_body={"code": "c"}))
    assert offline.status == 502


@pytest.mark.anyio
async def test_me_reports_app_id_so_the_page_can_call_requestauthcode() -> None:
    """``tt.requestAuthCode`` 需要 appId; 从这里下发, 同一份 dist 才能对不同应用跑起来。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_public_id", app_secret="s3cr3t-value")
    resp = await fw.handle_me(_request("GET", "/feishu/app/me", auth=auth))
    body = _payload(resp)
    assert body["authenticated"] is False
    assert body["app_id"] == "cli_public_id"
    # app_id 是公开的 (授权 URL 里就有), app_secret 不是。
    assert "s3cr3t-value" not in (resp.text or "")


@pytest.mark.anyio
async def test_seed_user_md_writes_the_feishu_name_into_the_workspace(tmp_path: Any) -> None:
    """USER.md 是 agent 读用户画像的地方; 身份该落在那里, 而不是只留在内存。"""
    wrote = await fw.seed_user_md(str(tmp_path), fw.FeishuUserInfo(open_id="ou_abc", name="张三"))
    assert wrote is True
    body = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "张三" in body
    assert "ou_abc" in body


@pytest.mark.anyio
async def test_seed_user_md_never_overwrites_what_the_agent_has_learned(tmp_path: Any) -> None:
    """最要紧的一条: USER.md 会被 agent 长期增补, 每次登录覆盖等于定期擦掉它的记忆。"""
    target = tmp_path / "USER.md"
    target.write_text("# USER.md\n\n- **Name:** 已知的名字\n- 喜欢简短回答\n", encoding="utf-8")

    wrote = await fw.seed_user_md(str(tmp_path), fw.FeishuUserInfo(open_id="ou_abc", name="张三"))
    assert wrote is False
    kept = target.read_text(encoding="utf-8")
    assert "喜欢简短回答" in kept
    assert "张三" not in kept


@pytest.mark.anyio
async def test_seed_user_md_leaves_the_name_blank_rather_than_inventing_one(tmp_path: Any) -> None:
    """飞书不保证给名字。编一个占位名会让 agent 拿假名字称呼真人。"""
    assert await fw.seed_user_md(str(tmp_path), fw.FeishuUserInfo(open_id="ou_abc")) is True
    body = (tmp_path / "USER.md").read_text(encoding="utf-8")
    assert "ou_abc" in body
    assert "unknown" in body.lower()


@pytest.mark.anyio
async def test_seed_user_md_is_a_noop_without_a_workspace_or_identity(tmp_path: Any) -> None:
    assert await fw.seed_user_md("", fw.FeishuUserInfo(open_id="ou_abc", name="张三")) is False
    assert await fw.seed_user_md(str(tmp_path), fw.FeishuUserInfo(open_id="")) is False
    assert not (tmp_path / "USER.md").exists()


@pytest.mark.anyio
async def test_me_seeds_user_md_in_the_session_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """按人播种: workspace 由 open_id 决定, 所以名字不会写进别人的档案。"""
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_NAME", "李四")
    fm = _FakeFeishuManager()
    _socket, session_id = await fm.route("ou_demo")
    ws = tmp_path / "ou_demo"

    resp = await fw.handle_me(
        _request(
            "GET",
            "/feishu/app/me",
            auth=fw.FeishuWebAppAuth(),
            fm=fm,
            sm=_FakeSessionManager({session_id: str(ws)}),
        )
    )
    assert _payload(resp)["authenticated"] is True
    assert "李四" in (ws / "USER.md").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_me_still_succeeds_when_user_md_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """写档案失败不该把人挡在工作台外面 —— 登录与画像是两件事。"""
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")

    async def _boom(*_: Any, **__: Any) -> bool:
        raise OSError("disk on fire")

    monkeypatch.setattr(fw, "seed_user_md", _boom)
    resp = await fw.handle_me(
        _request("GET", "/feishu/app/me", auth=fw.FeishuWebAppAuth(), fm=_FakeFeishuManager(), sm=_FakeSessionManager())
    )
    assert resp.status == 200
    assert _payload(resp)["authenticated"] is True


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        ("Mozilla/5.0 ... Lark/7.20.9 LarkLocale/zh_CN", "feishu"),
        ("Mozilla/5.0 ... Feishu/7.20.9", "feishu"),
        ("Mozilla/5.0 (Windows NT 10.0) Chrome/140.0 Safari/537.36", "browser"),
        ("", "browser"),
    ],
)
def test_detect_client_separates_the_feishu_webview_from_a_plain_browser(user_agent: str, expected: str) -> None:
    """一个 URL 同时是 2B 与 2C, UA 是服务端唯一能区分两者的线索。"""
    assert fw.detect_client(user_agent) == expected


@pytest.mark.anyio
async def test_me_reports_the_client_even_when_unauthenticated() -> None:
    """页面靠它区分「在飞书里但没授权」(该跳登录) 与「本地桌面工作台」(不该打扰)。

    少了这个字段, 页面只能默默退回桌面模式 —— 那正是让人误以为「场景 3 坏了」的原因。
    """
    resp = await fw.handle_me(
        _request("GET", "/feishu/app/me", auth=fw.FeishuWebAppAuth(), user_agent="Lark/7.20 LarkLocale/zh_CN")
    )
    body = _payload(resp)
    assert body["authenticated"] is False
    assert body["client"] == "feishu"


@pytest.mark.anyio
async def test_me_reports_the_client_alongside_a_bound_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID", "ou_demo")
    resp = await fw.handle_me(
        _request(
            "GET",
            "/feishu/app/me",
            auth=fw.FeishuWebAppAuth(),
            fm=_FakeFeishuManager(),
            sm=_FakeSessionManager(),
            user_agent="Mozilla/5.0 Chrome/140.0",
        )
    )
    body = _payload(resp)
    assert body["authenticated"] is True
    # 浏览器里也可以是「已授权身份」—— 只是不在飞书客户端内, 徽标要如实显示。
    assert body["client"] == "browser"


@pytest.mark.anyio
async def test_me_reports_the_display_name_for_the_sidebar() -> None:
    """侧栏账户区要显示「这是谁」。名字在登录兑换时就有了, 不该让前端再要一次权限。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")
    sid = await auth.open_session("ou_demo", "张三")
    resp = await fw.handle_me(
        _request(
            "GET",
            "/feishu/app/me",
            auth=auth,
            fm=_FakeFeishuManager(),
            sm=_FakeSessionManager(),
            cookies={fw.COOKIE_NAME: sid},
        )
    )
    body = _payload(resp)
    assert body["authenticated"] is True
    assert body["name"] == "张三"


@pytest.mark.anyio
async def test_me_reports_an_empty_name_rather_than_omitting_the_field() -> None:
    """飞书不保证给名字。字段恒在且为空串, 前端才有一个明确的「回落到本地昵称」信号。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")
    sid = await auth.open_session("ou_demo")
    resp = await fw.handle_me(
        _request(
            "GET",
            "/feishu/app/me",
            auth=auth,
            fm=_FakeFeishuManager(),
            sm=_FakeSessionManager(),
            cookies={fw.COOKIE_NAME: sid},
        )
    )
    assert _payload(resp)["name"] == ""


@pytest.mark.anyio
async def test_js_config_signs_the_page_so_the_sdk_can_become_ready() -> None:
    """免登的前置一步: ``h5sdk.ready`` 只在 ``config`` 成功后才回调。

    这条守的是那个「卡片看起来坏了」的回归: 从不 config 时 ready 永不触发, 免登退化成
    整页跳转, 页面留在桌面模式, 于是场景 3 整条链路被 feishuSessionId 的门挡住。
    """
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="s3cr3t-value")

    async def _ticket() -> str:
        return "tkt-1"

    auth.jsapi_ticket = _ticket  # type: ignore[method-assign]
    resp = await fw.handle_js_config(
        _request("POST", "/feishu/app/js-config", auth=auth, json_body={"url": "https://x.example/spa-v2/"})
    )
    assert resp.status == 200
    body = _payload(resp)
    assert body["app_id"] == "cli_x"
    assert body["nonce_str"]
    # 签名必须是 SHA1(jsapi_ticket=…&noncestr=…&timestamp=…&url=…) —— 键序由飞书规定。
    raw = f"jsapi_ticket=tkt-1&noncestr={body['nonce_str']}&timestamp={body['timestamp']}&url=https://x.example/spa-v2/"
    assert body["signature"] == hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()
    # ticket 与 app_secret 都不该出现在响应里 —— 页面只需要那个单向签名。
    assert "s3cr3t-value" not in (resp.text or "")
    assert "tkt-1" not in (resp.text or "")


@pytest.mark.anyio
async def test_js_config_strips_the_fragment_because_feishu_signs_the_bare_url() -> None:
    """``#`` 之后的部分不参与签名; 漏一个锚点就让 config 静默失败。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _ticket() -> str:
        return "tkt-1"

    auth.jsapi_ticket = _ticket  # type: ignore[method-assign]
    with_hash = await fw.handle_js_config(
        _request("POST", "/feishu/app/js-config", auth=auth, json_body={"url": "https://x.example/p#/task/1"})
    )
    bare = _payload(with_hash)
    raw = f"jsapi_ticket=tkt-1&noncestr={bare['nonce_str']}&timestamp={bare['timestamp']}&url=https://x.example/p"
    assert bare["signature"] == hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"url": "  "}, _BAD_JSON, []])
async def test_js_config_rejects_a_request_without_a_url(payload: Any) -> None:
    """URL 是签名的一部分, 服务端无从猜测 (``Referer`` 可缺失且带 ``#``)。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _boom() -> str:  # pragma: no cover - 不该被调用
        raise AssertionError("jsapi_ticket must not be fetched without a url")

    auth.jsapi_ticket = _boom  # type: ignore[method-assign]
    resp = await fw.handle_js_config(_request("POST", "/feishu/app/js-config", auth=auth, json_body=payload))
    assert resp.status == 400


@pytest.mark.anyio
async def test_js_config_without_credentials_is_501_so_the_page_falls_back() -> None:
    resp = await fw.handle_js_config(
        _request("POST", "/feishu/app/js-config", auth=fw.FeishuWebAppAuth(), json_body={"url": "https://x/y"})
    )
    assert resp.status == 501


@pytest.mark.anyio
async def test_js_config_maps_a_refusal_to_400_and_a_network_fault_to_502() -> None:
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _refused() -> str:
        raise ValueError("未取到 jsapi_ticket: code=99991663")

    auth.jsapi_ticket = _refused  # type: ignore[method-assign]
    refused = await fw.handle_js_config(
        _request("POST", "/feishu/app/js-config", auth=auth, json_body={"url": "https://x/y"})
    )
    assert refused.status == 400

    async def _offline() -> str:
        raise TimeoutError

    auth.jsapi_ticket = _offline  # type: ignore[method-assign]
    offline = await fw.handle_js_config(
        _request("POST", "/feishu/app/js-config", auth=auth, json_body={"url": "https://x/y"})
    )
    assert offline.status == 502


@pytest.mark.anyio
async def test_cookie_is_samesite_none_over_https_so_the_feishu_iframe_keeps_it() -> None:
    """飞书客户端把网页应用装进跨站 iframe: ``Lax`` 的 cookie 在那里连 ``Set-Cookie`` 都会被丢。

    没有 cookie 就没有身份, 没有身份场景 3 的卡永远不渲染 —— 这是「浏览器里好、飞书里坏」
    的另一半原因。
    """
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _exchange(code: str) -> fw.FeishuUserInfo:
        return fw.FeishuUserInfo(open_id="ou_from_js", name="张三")

    auth.exchange_js_code = _exchange  # type: ignore[method-assign]
    resp = await fw.handle_js_login(
        _request(
            "POST",
            "/feishu/app/js-login",
            auth=auth,
            json_body={"code": "c"},
            forwarded_proto="https",
        )
    )
    cookie = str(resp.cookies[fw.COOKIE_NAME]).lower()
    assert "samesite=none" in cookie
    # SameSite=None 没有 Secure 会被浏览器整条丢弃, 所以这两个必须成对出现。
    assert "secure" in cookie
    assert "httponly" in cookie


@pytest.mark.anyio
async def test_cookie_stays_lax_over_plain_http_so_the_desktop_flow_is_untouched() -> None:
    """本机桌面流程走 ``http://127.0.0.1``: 那里 ``Secure`` 会让 cookie 根本存不下。"""
    auth = fw.FeishuWebAppAuth(app_id="cli_x", app_secret="secret")

    async def _exchange(code: str) -> fw.FeishuUserInfo:
        return fw.FeishuUserInfo(open_id="ou_from_js")

    auth.exchange_js_code = _exchange  # type: ignore[method-assign]
    resp = await fw.handle_js_login(_request("POST", "/feishu/app/js-login", auth=auth, json_body={"code": "c"}))
    cookie = str(resp.cookies[fw.COOKIE_NAME]).lower()
    assert "samesite=lax" in cookie
    assert "secure" not in cookie
