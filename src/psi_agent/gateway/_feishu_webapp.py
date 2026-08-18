"""飞书网页应用 (工作台) 身份层 —— 让浏览器里的 SPA 和机器人落在**同一个 Session** 上。

问题: `spa-v2` 自己不知道访问者是谁。桌面版靠用户手选 workspace 目录; 飞书网页应用里不能这样
——用户没有本机路径可选, 而且必须看到**自己**那份任务/交付物, 不是别人的。

机器人侧早已有权威路由: ``POST /feishu/route`` 按 ``open_id`` 幂等地换到 Session
(``_feishu_manager``)。所以本模块只补两件事:

1. **拿到 open_id** —— 两条路, 都在服务端用 ``app_secret`` 把 ``code`` 换成身份:

   * **JSSDK 免登** (页面开在飞书客户端里): 前端 ``tt.requestAuthCode`` 拿一个免登码,
     ``POST /feishu/app/js-login`` 把它换成 ``open_id``。**没有页面跳转**, 用户零点击。
   * **授权码回跳** (页面开在普通浏览器里): ``/feishu/app/login`` → 飞书 →
     ``/feishu/app/callback``。

2. **把身份钉在会话上** —— 发一个 HttpOnly cookie, 随后 ``/feishu/app/me`` 用它调
   ``fm.route(open_id)`` 得到与机器人**同一个** ``session_id`` 和 workspace。

刻意**不用** ``tt.getUserInfo``: 那条路要先做 ``h5sdk.config`` 签名 (tenant_access_token →
jsapi_ticket → SHA1), 换来的却是**浏览器自己声称**的身份 —— 前端可以随便改。免登码相反:
它对浏览器不透明, 只有握着 ``app_secret`` 的服务端能把它兑成 ``open_id``。所以签名那一整套
在这里是纯负担, 而 ``open_id`` 的来源始终只有一个: 飞书对服务端的回答。

于是 SPA 现有的 ``/sessions/{id}/history`` / ``/todos`` / ``/workspace/*`` 不必改动, 读到的就是
机器人产出的东西; 用户画像 / llm_wiki / Supervisor 都是那个 workspace 下的文件, 自然共享。

**刻意不做的事**: ``app_secret`` 与 ``user_access_token`` 绝不出现在任何响应体里, 也不落盘;
cookie 里只有一枚不透明随机 sid, ``sid → open_id`` 存进程内存。因此重启 Gateway 即需重新授权
——这是有意的取舍 (无持久化 = 无泄露面), 与 ``_oauth_manager`` 的一次性信箱同一思路。
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import aiohttp
import anyio
from aiohttp import web
from loguru import logger

_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)

# JSSDK 免登: 免登码只能配 app_access_token 兑换 (不是 tenant_, 也不是 v2/oauth/token ——
# 后者要的是 authorize 回跳那种 code, 拿免登码去换会被拒)。
_APP_ACCESS_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
_JS_LOGIN_URL = "https://open.feishu.cn/open-apis/authen/v1/access_token"

# ``h5sdk.config`` 的鉴权材料。免登码那条路要先 config 成功, SDK 才会 ready ——
# 见 ``handle_js_config`` 的 docstring。ticket 只能用 tenant_access_token 取。
_TENANT_ACCESS_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_JSSDK_TICKET_URL = "https://open.feishu.cn/open-apis/jssdk/ticket/get"
# 飞书给的 ticket 有效期 7200s 且接口有频控, 故进程内缓存。留 300s 余量避免用到刚过期的。
_TICKET_TTL_SECONDS = 7200.0
_TICKET_SAFETY_MARGIN = 300.0

COOKIE_NAME = "psi_feishu_sid"
# 授权往返通常几秒; 5 分钟足够宽松, 又不留长期悬挂的 state。
_STATE_TTL_SECONDS = 300.0
# 会话 cookie 的有效期。飞书网页应用一般在客户端里长时间挂着, 8 小时覆盖一个工作日。
_SESSION_TTL_SECONDS = 8 * 60 * 60.0
_MAX_PENDING_STATES = 256
_MAX_SESSIONS = 512


@dataclass
class _PendingState:
    """一次授权往返的防 CSRF 凭据 (一次取走即删)。"""

    created_at: float


@dataclass(frozen=True)
class FeishuUserInfo:
    """一次身份兑换的结果。``name`` 可能为空 —— 飞书不保证给。

    为什么带上 ``name``: 它在兑换响应里**本来就有**, 丢掉它就只能再调一次 contact 接口
    (还要额外的 ``contact:user.base:readonly`` 权限) 才能知道用户叫什么。而 USER.md 需要
    一个能称呼人的名字, 不是一串 ``ou_``。
    """

    open_id: str
    name: str = ""


@dataclass
class _WebSession:
    open_id: str
    created_at: float
    name: str = ""


@dataclass(frozen=True)
class JsConfig:
    """``h5sdk.config`` 要的四件套。``signature`` 与页面 URL 绑定, 故不可跨页复用。"""

    app_id: str
    timestamp: int
    nonce_str: str
    signature: str


@dataclass
class _CachedTicket:
    """一枚 ``jsapi_ticket`` 及其取得时间 (飞书侧 7200s 有效, 且接口有频控)。"""

    ticket: str
    fetched_at: float


@dataclass
class FeishuWebAppAuth:
    """按 cookie 把浏览器会话映射到飞书 ``open_id`` (进程内存, 不持久化)。"""

    app_id: str = ""
    app_secret: str = ""
    _ticket: _CachedTicket | None = None
    _states: dict[str, _PendingState] = field(default_factory=dict)
    _sessions: dict[str, _WebSession] = field(default_factory=dict)
    _lock: anyio.Lock = field(default_factory=anyio.Lock)

    @property
    def configured(self) -> bool:
        """凭据齐备才可能走真实授权; 否则只剩 mock 模式。"""
        return bool(self.app_id and self.app_secret)

    def _sweep(self, now: float) -> None:
        """就地清理过期 state / 会话 (调用方须持锁)。"""
        for key in [s for s, p in self._states.items() if now - p.created_at > _STATE_TTL_SECONDS]:
            del self._states[key]
        for key in [s for w in (self._sessions,) for s, v in w.items() if now - v.created_at > _SESSION_TTL_SECONDS]:
            del self._sessions[key]

    async def issue_state(self) -> str:
        """生成并暂存一枚 state, 供 authorize 往返防 CSRF。"""
        state = secrets.token_urlsafe(24)
        now = time.monotonic()
        async with self._lock:
            self._sweep(now)
            if len(self._states) >= _MAX_PENDING_STATES:
                oldest = min(self._states, key=lambda s: self._states[s].created_at)
                del self._states[oldest]
                logger.warning("FeishuWebAppAuth: state 过多, 丢弃最旧的一枚")
            self._states[state] = _PendingState(created_at=now)
        return state

    async def consume_state(self, state: str) -> bool:
        """校验并**删除** state; 未命中或已过期返回 ``False``。"""
        if not state:
            return False
        now = time.monotonic()
        async with self._lock:
            self._sweep(now)
            return self._states.pop(state, None) is not None

    async def open_session(self, open_id: str, name: str = "") -> str:
        """为 ``open_id`` 建立浏览器会话, 返回要写进 cookie 的 sid。"""
        if not open_id:
            raise ValueError("open_id must not be empty")
        sid = secrets.token_urlsafe(32)
        now = time.monotonic()
        async with self._lock:
            self._sweep(now)
            if len(self._sessions) >= _MAX_SESSIONS:
                oldest = min(self._sessions, key=lambda s: self._sessions[s].created_at)
                del self._sessions[oldest]
                logger.warning("FeishuWebAppAuth: 会话过多, 踢掉最旧的一个")
            self._sessions[sid] = _WebSession(open_id=open_id, created_at=now, name=name)
        return sid

    async def resolve(self, sid: str) -> str:
        """cookie → ``open_id``; 无效或过期返回空串。"""
        if not sid:
            return ""
        now = time.monotonic()
        async with self._lock:
            self._sweep(now)
            found = self._sessions.get(sid)
            return found.open_id if found else ""

    async def resolve_user(self, sid: str) -> FeishuUserInfo | None:
        """cookie → ``(open_id, name)``; 无效或过期返回 ``None``。

        与 ``resolve`` 并存而不是替换它: 调用方多数只关心「是谁」, 只有写 USER.md 的那条
        路径才需要名字。
        """
        if not sid:
            return None
        now = time.monotonic()
        async with self._lock:
            self._sweep(now)
            found = self._sessions.get(sid)
            if found is None:
                return None
            return FeishuUserInfo(open_id=found.open_id, name=found.name)

    async def close_session(self, sid: str) -> None:
        async with self._lock:
            self._sessions.pop(sid, None)

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        query = urlencode({"client_id": self.app_id, "redirect_uri": redirect_uri, "state": state})
        return f"{_AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str, redirect_uri: str) -> FeishuUserInfo:
        """``code`` → ``(open_id, name)``。两跳都在服务端完成, 令牌不出本进程。"""
        async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as http:
            payload = {
                "grant_type": "authorization_code",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
            async with http.post(_TOKEN_URL, json=payload) as resp:
                token_body = await resp.json(content_type=None)
            if not isinstance(token_body, dict):
                raise ValueError("飞书 token 接口返回了非 JSON 对象")
            token = token_body.get("access_token") or ""
            if not token:
                # 只带回飞书的错误码/描述, 不回显请求体 (内含 client_secret)。
                raise ValueError(f"换取 access_token 失败: code={token_body.get('code')} {token_body.get('error')}")

            headers = {"Authorization": f"Bearer {token}"}
            async with http.get(_USER_INFO_URL, headers=headers) as resp:
                info_body = await resp.json(content_type=None)
        if not isinstance(info_body, dict):
            raise ValueError("飞书 user_info 接口返回了非 JSON 对象")
        data = info_body.get("data")
        open_id = data.get("open_id") if isinstance(data, dict) else ""
        if not isinstance(open_id, str) or not open_id:
            raise ValueError(f"user_info 未返回 open_id: code={info_body.get('code')}")
        return FeishuUserInfo(open_id=open_id, name=_pick_name(data))

    async def jsapi_ticket(self) -> str:
        """取 ``jsapi_ticket`` (进程内缓存)。

        两跳: ``tenant_access_token`` → ``jssdk/ticket/get``。刻意缓存 —— 飞书侧 ticket
        有效期 7200s 且该接口有频控, 每次 config 都重新取会在多标签页时被限流。
        """
        now = time.monotonic()
        async with self._lock:
            cached = self._ticket
            if cached and now - cached.fetched_at < _TICKET_TTL_SECONDS - _TICKET_SAFETY_MARGIN:
                return cached.ticket

        async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as http:
            payload = {"app_id": self.app_id, "app_secret": self.app_secret}
            async with http.post(_TENANT_ACCESS_TOKEN_URL, json=payload) as resp:
                token_body = await resp.json(content_type=None)
            if not isinstance(token_body, dict):
                raise ValueError("飞书 tenant_access_token 接口返回了非 JSON 对象")
            token = token_body.get("tenant_access_token") or ""
            if not token:
                # 同 exchange_code: 只回显飞书的错误码/描述, 请求体里有 app_secret。
                code = token_body.get("code")
                raise ValueError(f"换取 tenant_access_token 失败: code={code} {token_body.get('msg')}")

            headers = {"Authorization": f"Bearer {token}"}
            async with http.post(_JSSDK_TICKET_URL, json={}, headers=headers) as resp:
                ticket_body = await resp.json(content_type=None)
        if not isinstance(ticket_body, dict):
            raise ValueError("飞书 jssdk ticket 接口返回了非 JSON 对象")
        data = ticket_body.get("data")
        ticket = data.get("ticket") if isinstance(data, dict) else ""
        if not isinstance(ticket, str) or not ticket:
            raise ValueError(f"未取到 jsapi_ticket: code={ticket_body.get('code')} {ticket_body.get('msg')}")

        async with self._lock:
            self._ticket = _CachedTicket(ticket=ticket, fetched_at=time.monotonic())
        return ticket

    async def js_config(self, url: str) -> JsConfig:
        """为 ``url`` 这一页算出 ``h5sdk.config`` 的鉴权材料。

        签名串的键序是**固定**的 (飞书按字面校验), 且 ``url`` 必须与页面地址逐字一致、
        去掉 ``#`` 之后的部分 —— 这两条任一不符, config 就会失败, 于是 SDK 永远不 ready。
        ``nonce_str`` 每次现生成: 复用一个常量等于没有 nonce。
        """
        ticket = await self.jsapi_ticket()
        # 飞书的示例用毫秒时间戳; 与签名串里的值必须是同一个, 故只取一次。
        timestamp = int(time.time() * 1000)
        nonce_str = secrets.token_urlsafe(12)
        raw = f"jsapi_ticket={ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
        # SHA1 是飞书这个接口规定的算法, 不是我们的选择 —— 此处它当校验和用, 不作密码学承诺。
        signature = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()
        return JsConfig(app_id=self.app_id, timestamp=timestamp, nonce_str=nonce_str, signature=signature)

    async def exchange_js_code(self, code: str) -> FeishuUserInfo:
        """JSSDK 免登码 → ``(open_id, name)`` (两跳都在服务端: app_access_token, 再兑码)。

        与 ``exchange_code`` 的差别只在换码那一跳: 免登码走 ``authen/v1/access_token`` +
        ``Bearer app_access_token``, 且**没有** ``redirect_uri`` —— 客户端里根本没有回跳。
        ``open_id`` 直接在这一跳的响应里, 所以不必再调 user_info。
        """
        async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as http:
            app_payload = {"app_id": self.app_id, "app_secret": self.app_secret}
            async with http.post(_APP_ACCESS_TOKEN_URL, json=app_payload) as resp:
                app_body = await resp.json(content_type=None)
            if not isinstance(app_body, dict):
                raise ValueError("飞书 app_access_token 接口返回了非 JSON 对象")
            app_token = app_body.get("app_access_token") or ""
            if not app_token:
                # 同 exchange_code: 只回显飞书的错误码/描述, 请求体里有 app_secret。
                raise ValueError(f"换取 app_access_token 失败: code={app_body.get('code')} {app_body.get('msg')}")

            headers = {"Authorization": f"Bearer {app_token}"}
            body = {"grant_type": "authorization_code", "code": code}
            async with http.post(_JS_LOGIN_URL, json=body, headers=headers) as resp:
                login_body = await resp.json(content_type=None)
        if not isinstance(login_body, dict):
            raise ValueError("飞书免登接口返回了非 JSON 对象")
        data = login_body.get("data")
        open_id = data.get("open_id") if isinstance(data, dict) else ""
        if not isinstance(open_id, str) or not open_id:
            raise ValueError(f"免登码未换到 open_id: code={login_body.get('code')} {login_body.get('msg')}")
        return FeishuUserInfo(open_id=open_id, name=_pick_name(data))


def _pick_name(data: Any) -> str:
    """从飞书身份响应里挑一个能称呼人的名字。

    优先 ``name`` (用户在租户里的显示名), 退而取 ``en_name``。两者都可能缺 —— 取决于应用
    拿到的 scope 与用户资料填得多全 —— 所以拿不到就返回空串, 由调用方决定怎么退化。
    """
    if not isinstance(data, dict):
        return ""
    for key in ("name", "en_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_loopback(request: web.Request) -> bool:
    """请求是否来自本机。mock 模式只对本机开放, 免得成为一个匿名冒充任何人的入口。"""
    peer = request.remote or ""
    if peer in {"localhost", "::1"}:
        return True
    try:
        return ipaddress.ip_address(peer).is_loopback
    except ValueError:
        return False


def mock_open_id() -> str:
    """``PSI_FEISHU_WEBAPP_MOCK_OPEN_ID``: 未注册应用前也能本机演示整条链路。"""
    return (os.environ.get("PSI_FEISHU_WEBAPP_MOCK_OPEN_ID") or "").strip()


def mock_name() -> str:
    """``PSI_FEISHU_WEBAPP_MOCK_NAME``: mock 模式下 USER.md 里的名字 (可缺省)。"""
    return (os.environ.get("PSI_FEISHU_WEBAPP_MOCK_NAME") or "").strip()


def _redirect_uri(request: web.Request) -> str:
    """回调地址必须与飞书开发者后台登记的完全一致, 故按当前请求的 host 拼。"""
    return str(request.url.origin()) + "/feishu/app/callback"


def _cross_site_cookie(request: web.Request) -> bool:
    """这个请求是否需要 ``SameSite=None`` 的 cookie。

    飞书客户端会把网页应用装进一个 **跨站 iframe**。那种上下文里 ``SameSite=Lax`` 的
    cookie 既发不出去, ``Set-Cookie`` 也会被浏览器直接丢掉 —— 于是 ``/feishu/app/me``
    永远答 ``authenticated: false``, 页面默默退回桌面模式, 看起来就像「卡片坏了」。

    ``SameSite=None`` 必须搭配 ``Secure``, 而 ``Secure`` 只在 HTTPS 上成立。所以这里
    按**当前请求是不是 HTTPS** 来决定: 是则放宽到 None+Secure (工作台部署形态), 否则
    维持 Lax —— 本机 ``http://127.0.0.1`` 的桌面流程行为完全不变。
    """
    forwarded = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
    return (forwarded or request.scheme) == "https"


def _set_cookie(response: web.StreamResponse, sid: str, *, cross_site: bool = False) -> None:
    """HttpOnly: JS 读不到, 因此 XSS 也偷不走身份。

    ``cross_site`` 为真时发 ``SameSite=None; Secure`` —— 飞书客户端的跨站 iframe 里只有
    这一种 cookie 收得下。否则用 ``Lax``: 够授权跳转回来带得上, 又不必要求 HTTPS。
    """
    response.set_cookie(
        COOKIE_NAME,
        sid,
        httponly=True,
        samesite="None" if cross_site else "Lax",
        secure=cross_site,
        max_age=int(_SESSION_TTL_SECONDS),
        path="/",
    )


def detect_client(user_agent: str) -> str:
    """UA → ``"feishu"`` (飞书/Lark 客户端内置 webview) 或 ``"browser"``。

    这是**唯一**能区分「页面开在飞书客户端里」与「开在普通浏览器里」的服务端信号: cookie
    只能证明「有人过了飞书授权」, 证明不了页面此刻在哪个客户端里。飞书/Lark 的 webview 会
    在 UA 里带上 ``Lark``(国际版) 或 ``Feishu``; 桌面客户端还会带 ``LarkLocale``。

    刻意只做**提示**用途, 不做鉴权: UA 可以伪造, 所以它决定的是显示什么模式徽标, 而
    ``open_id`` 依旧只来自 HttpOnly cookie。真正的客户端能力检测要靠前端 JSSDK
    (``window.h5sdk`` / ``window.tt``), 那是浏览器侧的事。
    """
    ua = user_agent.lower()
    if "lark" in ua or "feishu" in ua:
        return "feishu"
    return "browser"


async def resolve_request_open_id(request: web.Request) -> str:
    """cookie → ``open_id``; 空串表示未登录。

    身份**只**从 HttpOnly cookie 解析, 绝不看 query/body —— 否则任何人都能带上别人的
    ``open_id`` 去读写别人的 workspace。此前 ``handle_me`` 与 ``_outreach_api`` 各写了一遍
    这段, 第三个调用方 (``/feishu/app/sessions``) 是收敛它的时机: 这条判定漂移一次就是
    越权, 不是美观问题。
    """
    auth = request.app.get("feishu_webapp")
    if auth is None:
        return ""
    return await auth.resolve(request.cookies.get(COOKIE_NAME, ""))


async def handle_login(request: web.Request) -> web.StreamResponse:
    """跳转到飞书授权页。凭据缺失时 501, 让前端知道"这台 Gateway 没配网页应用"。"""
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    if not auth.configured:
        return web.json_response(
            {"error": "飞书网页应用未配置: 需要 PSI_FEISHU_APP_ID / PSI_FEISHU_APP_SECRET"},
            status=501,
        )
    state = await auth.issue_state()
    raise web.HTTPFound(auth.authorize_url(_redirect_uri(request), state))


async def handle_callback(request: web.Request) -> web.StreamResponse:
    """飞书带 ``code`` 跳回: 校验 state → 换 open_id → 发 cookie → 回到工作台。"""
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    error = request.query.get("error") or ""
    if error:
        return web.json_response({"error": f"飞书授权被拒绝: {error}"}, status=400)
    code = request.query.get("code") or ""
    state = request.query.get("state") or ""
    if not code:
        return web.json_response({"error": "回调缺少 code"}, status=400)
    # state 先于任何网络调用校验: 校验失败说明这不是我们发起的授权。
    if not await auth.consume_state(state):
        return web.json_response({"error": "state 无效或已过期"}, status=400)
    try:
        user = await auth.exchange_code(code, _redirect_uri(request))
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning(f"飞书网页应用换取身份失败 (网络): {exc!r}")
        return web.json_response({"error": "连接飞书失败, 请重试"}, status=502)
    except ValueError as exc:
        logger.warning(f"飞书网页应用换取身份失败: {exc!r}")
        return web.json_response({"error": str(exc)}, status=400)
    sid = await auth.open_session(user.open_id, user.name)
    logger.info(f"飞书网页应用登录成功 open_id={user.open_id[:8]}…")
    response = web.HTTPFound("/spa-v2/index.html")
    _set_cookie(response, sid, cross_site=_cross_site_cookie(request))
    return response


_IDENTITY_MARKER = "<!-- psi:feishu-identity -->"

_USER_MD_TEMPLATE = """\
# USER.md — About Your Human

{marker}
- **Name:** {name}
- **What to call them:** {name}
- **Pronouns:** _(unknown — use they/them until they say otherwise)_
- **Timezone:**
- **Feishu open_id:** `{open_id}`
- **Notes:** Identity came from Feishu sign-in, not from the person telling you.
  Treat the name as how their workspace lists them; if they introduce themselves
  differently, believe them and update this file.

## Context

_(What do they care about? What projects are they working on? What annoys them?
Build this over time.)_
"""


async def seed_user_md(workspace: str, user: FeishuUserInfo) -> bool:
    """把飞书身份写进 workspace 的 ``USER.md``。已存在就**不动**, 返回是否写了。

    为什么只在缺失时写: ``USER.md`` 是 agent 会自己长期增补的档案 (agent 包里的模板就写着
    "Update this as you go")。每次登录都覆盖等于把它积累的东西定期擦掉 —— 身份只是**起点**,
    不是每轮真理。

    刻意只写名字与 ``open_id``: 这两样在登录时本来就有。手机号/邮箱之类要额外 scope, 而且
    落到磁盘上就成了长期负担, 不是这个功能需要的东西。

    失败返回 ``False`` 且不抛: 登录成功与否不该取决于能不能写一个档案文件。
    """
    if not workspace or not user.open_id:
        return False
    target = anyio.Path(workspace) / "USER.md"
    try:
        if await target.exists():
            return False
        await target.parent.mkdir(parents=True, exist_ok=True)
        body = _USER_MD_TEMPLATE.format(
            marker=_IDENTITY_MARKER,
            # 名字可能拿不到 (scope/资料所限)。留白比编一个占位名好: 后者会让 agent
            # 把假名字当真名用。
            name=user.name or "_(unknown — ask them)_",
            open_id=user.open_id,
        )
        await target.write_text(body, encoding="utf-8")
    except OSError as exc:
        logger.warning(f"写 USER.md 失败 (不影响登录): {exc!r}")
        return False
    logger.info(f"已按飞书身份初始化 USER.md: {target}")
    return True


async def handle_me(request: web.Request) -> web.StreamResponse:
    """SPA 启动时唯一要问的问题: 我是谁, 该打开哪个 Session。

    命中身份即调 ``fm.route(open_id)`` —— 与机器人**同一条**幂等路由, 所以拿到的
    ``session_id`` / workspace 就是机器人那一份。
    """
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    identity = await auth.resolve_user(request.cookies.get(COOKIE_NAME, ""))
    open_id = identity.open_id if identity else ""
    response_cookie = ""
    if not open_id:
        # mock 模式: 本机演示时免去授权往返, 直接以指定 open_id 落座。
        mock = mock_open_id()
        if mock:
            if not _is_loopback(request):
                return web.json_response({"error": "mock 模式仅对本机开放"}, status=403)
            open_id = mock
            identity = FeishuUserInfo(open_id=open_id, name=mock_name())
            response_cookie = await auth.open_session(open_id, identity.name)
    # 未登录也要带上 client: 页面靠它决定「在飞书客户端里却没身份」时直接去授权,
    # 而不是默默退回桌面模式 (那正是让人以为场景 3 坏了的原因)。
    client = detect_client(request.headers.get("User-Agent", ""))
    if not open_id:
        payload: dict[str, Any] = {
            "authenticated": False,
            "configured": auth.configured,
            "client": client,
            # app_id 是公开值 (它就写在授权 URL 的 query 里), 前端 tt.requestAuthCode 要用。
            # 从这里下发而不是打进构建产物: 同一份 dist 能对不同应用/租户跑起来。
            "app_id": auth.app_id,
        }
        return web.json_response(payload)

    fm = request.app.get("fm")
    if fm is None:
        return web.json_response({"error": "Gateway 未启用飞书路由"}, status=501)
    try:
        _socket, session_id = await fm.route(open_id)
    except Exception as exc:
        logger.error(f"飞书网页应用绑定 Session 失败: {exc!r}")
        return web.json_response({"error": f"绑定 Session 失败: {exc}"}, status=500)
    sm = request.app.get("sm")
    workspace = ""
    if sm is not None:
        try:
            workspace = str(sm.get_workspace(session_id) or "")
        except Exception:  # workspace 只是便利信息, 拿不到不该让整个请求失败
            workspace = ""

    # workspace 是每个 open_id 各自一份 (``_feishu_manager._workspace_for``), 所以在这里播种
    # USER.md 天然是**按人**的, 不会把某人的名字写到别人的档案里。放在这一步而不是登录那一步:
    # 只有 fm.route 之后才知道目录在哪。
    if workspace and identity is not None:
        # 兜住一切: 播种档案是**附带**动作, 任何失败都不该把人挡在工作台外面。
        # ``seed_user_md`` 自己已吞掉 OSError, 这层管的是它没预料到的那些。
        try:
            await seed_user_md(workspace, identity)
        except Exception as exc:
            logger.warning(f"播种 USER.md 失败 (不影响登录): {exc!r}")
    result = web.json_response(
        {
            "authenticated": True,
            "open_id": open_id,
            "session_id": session_id,
            "workspace": workspace,
            # 侧栏要显示「这是谁」。名字在登录兑换时**本来就拿到了** (见 FeishuUserInfo),
            # 从这里下发免去前端再要一次 contact 权限。可能为空 —— 飞书不保证给,
            # 那时页面自己回落到本地昵称。
            "name": identity.name if identity else "",
            # "feishu" = 页面开在飞书客户端里; "browser" = 普通浏览器 (仍然是已授权身份,
            # 只是不在客户端内)。页面用它显示模式徽标, 不用它做任何鉴权决定。
            "client": client,
        }
    )
    if response_cookie:
        _set_cookie(result, response_cookie, cross_site=_cross_site_cookie(request))
    return result


async def handle_js_login(request: web.Request) -> web.StreamResponse:
    """JSSDK 免登: 前端 ``tt.requestAuthCode`` 的码 → cookie 身份, **不跳页面**。

    这是飞书客户端里的首选路径。授权码回跳在客户端内 webview 里体验很差 (整页跳走再跳回,
    偶尔还落到外部浏览器); 免登码则是当场换完, 用户一次点击都不用。

    没有 state 校验: 免登码不是浏览器重定向拿到的, 不存在被诱导发起的授权往返, 所以没有
    可 CSRF 的东西。安全性落在别处 —— 码只能由握着 ``app_secret`` 的服务端兑换, 且一次性。
    """
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    if not auth.configured:
        return web.json_response(
            {"error": "飞书网页应用未配置: 需要 PSI_FEISHU_APP_ID / PSI_FEISHU_APP_SECRET"},
            status=501,
        )
    try:
        body = await request.json()
    except Exception:
        body = None
    code = str((body or {}).get("code") or "").strip() if isinstance(body, dict) else ""
    if not code:
        return web.json_response({"error": "缺少 code"}, status=400)
    try:
        user = await auth.exchange_js_code(code)
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning(f"飞书免登换取身份失败 (网络): {exc!r}")
        return web.json_response({"error": "连接飞书失败, 请重试"}, status=502)
    except ValueError as exc:
        logger.warning(f"飞书免登换取身份失败: {exc!r}")
        return web.json_response({"error": str(exc)}, status=400)
    sid = await auth.open_session(user.open_id, user.name)
    logger.info(f"飞书免登成功 open_id={user.open_id[:8]}…")
    # 只回 ok: open_id 与 session 由随后的 /feishu/app/me 统一给出, 免得两处各说一套。
    response = web.json_response({"ok": True})
    _set_cookie(response, sid, cross_site=_cross_site_cookie(request))
    return response


async def handle_js_config(request: web.Request) -> web.StreamResponse:
    """``h5sdk.config`` 的鉴权材料 —— 免登那条路的**前置**一步。

    为什么非要有它: ``h5sdk.ready`` 只在 ``config`` 成功之后才回调。此前的实现直接调
    ``ready`` 而从不 ``config``, 于是在飞书客户端里回调永远不来, ``requestAuthCode``
    卡到 4s 超时, 免登退化成整页跳转 —— 而那条兜底又要求 HTTPS + 已登记的可信域名,
    于是两条路一起断, 页面留在桌面模式, 场景 3 的卡看起来就像坏了。

    ``url`` 由页面给: 签名与页面地址绑定, 服务端无从得知 (``Referer`` 可缺失且带 ``#``)。
    它不是凭据 —— 拿别的 URL 来只会算出一个在**那个** URL 才成立的签名, 而 ``open_id``
    依旧只来自免登码兑换。所以这里不校验身份, 但仍要求凭据齐备。

    ``app_secret`` 不出现在响应里: 只回 appId / timestamp / nonceStr / signature 四样,
    签名是单向的, 从中反推不出 ticket 或密钥。
    """
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    if not auth.configured:
        return web.json_response(
            {"error": "飞书网页应用未配置: 需要 PSI_FEISHU_APP_ID / PSI_FEISHU_APP_SECRET"},
            status=501,
        )
    try:
        body = await request.json()
    except Exception:
        body = None
    url = str((body or {}).get("url") or "").strip() if isinstance(body, dict) else ""
    if not url:
        return web.json_response({"error": "缺少 url"}, status=400)
    # 与页面实际地址逐字一致才算得对, 而 ``#`` 之后的部分不参与签名 —— 前端已经去掉,
    # 这里再兜一次, 免得一个漏网的锚点让 config 悄悄失败。
    url = url.split("#")[0]
    try:
        config = await auth.js_config(url)
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning(f"取 jsapi_ticket 失败 (网络): {exc!r}")
        return web.json_response({"error": "连接飞书失败, 请重试"}, status=502)
    except ValueError as exc:
        logger.warning(f"取 jsapi_ticket 失败: {exc!r}")
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(
        {
            "app_id": config.app_id,
            "timestamp": config.timestamp,
            "nonce_str": config.nonce_str,
            "signature": config.signature,
        }
    )


async def handle_logout(request: web.Request) -> web.StreamResponse:
    auth: FeishuWebAppAuth = request.app["feishu_webapp"]
    await auth.close_session(request.cookies.get(COOKIE_NAME, ""))
    response = web.json_response({"authenticated": False})
    response.del_cookie(COOKIE_NAME, path="/")
    return response


def register(app: web.Application, *, app_id: str = "", app_secret: str = "") -> None:
    """挂上网页应用身份五件套。凭据可缺失: 那时只有 mock 模式可用。"""
    app["feishu_webapp"] = FeishuWebAppAuth(app_id=app_id, app_secret=app_secret)
    app.router.add_get("/feishu/app/login", handle_login)
    app.router.add_get("/feishu/app/callback", handle_callback)
    # 免登的前置一步: h5sdk.config 的签名。没有它 h5sdk.ready 不会回调。
    app.router.add_post("/feishu/app/js-config", handle_js_config)
    # 客户端内首选: 免登码换身份, 无跳转 (前端 tt.requestAuthCode)。
    app.router.add_post("/feishu/app/js-login", handle_js_login)
    app.router.add_get("/feishu/app/me", handle_me)
    app.router.add_post("/feishu/app/logout", handle_logout)
