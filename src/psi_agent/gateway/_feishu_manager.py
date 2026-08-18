"""FeishuManager — 「飞书会话 → Session」路由表, 复用 SessionManager 动态 spawn。

路由键按会话类型分两支:

* **私聊** (``chat_type`` 为 ``p2p``/缺失) —— 键是发送者 ``open_id``, 每人一个独立 Session,
  于是各自有隔离的历史/workspace/记忆。
* **群聊** (``chat_type`` 为 ``group``/``topic``) —— 键是 ``chat_id``, **整个群共用一个**
  Session。群里所有人对机器人说的话进同一条上下文, 机器人在群里因此有连贯记忆; 群与群、群
  与私聊之间互不串味。

两者都是**动态**的(事先不知道有哪些人/哪些群), 故某键首次路由时按需 spawn 一个 Session。

本模块是 gateway 侧「飞书会话 → Session」的唯一权威 —— channel 只把 ``open_id``/``chat_id``/
``chat_type`` 交给 Gateway 换 socket, 不再自己决定路由键与 ``ai_id``/``workspace``。Session
生命周期仍由 ``SessionManager`` 掌控。
"""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass, field

import anyio
from loguru import logger

from psi_agent._feishu_routing import route_key
from psi_agent.gateway._session_manager import SessionManager

_SOCKET_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

# 网页应用侧「一个用户开的第 N 个任务」的 session_id 中缀与随机尾巴 (6 字节 = 12 位十六进制:
# 短到能读, 又远超碰撞所需 —— 同一用户手动新建任务的量级是几十, 不是 2^48)。
_WEB_INFIX = "web"
_WEB_SUFFIX_BYTES = 6

# 子会话 id 的**精确**形状。中段刻意不许出现 ``-``: 私聊 open_id 派生时 ``-`` 已被转义成
# ``_`` (见 ``bot_session_id``), 所以这条正则既认得所有子会话, 又认不出任何规范 id ——
# 群聊那支 ``feishu-chat-<chat_id>`` 的 ``chat-`` 里带 ``-``, 一定落在中段之外。
_WEB_SESSION_RE = re.compile(rf"^feishu-[A-Za-z0-9._]+-{_WEB_INFIX}-[0-9a-f]{{{_WEB_SUFFIX_BYTES * 2}}}$")


def _sanitize_open_id(open_id: str) -> str:
    """把 open_id/chat_id 净化成安全的 socket/pipe/path 段。

    飞书 open_id/chat_id 本身即 ``[A-Za-z0-9_]``, 对其是恒等变换; 仅作防御层, 兜住
    union_id/user_id 等意外字符, 避免污染 session_id / workspace 目录名。
    """
    return _SOCKET_UNSAFE.sub("_", open_id)


def bot_session_id(open_id: str) -> str:
    """私聊 ``open_id`` → 机器人那个**权威** session_id。

    与 ``FeishuManager._session_id`` 同一派生 (那边按路由键, 这边只服务私聊)。单独导出是
    因为网页应用侧要能在**不**触发 spawn 的前提下问一句「机器人那张卡是哪个 id」——
    页面要把它从任务列表里摘掉。
    """
    return f"feishu-{_sanitize_open_id(open_id).replace('-', '_')}"


def web_session_id(open_id: str) -> str:
    """网页应用里新建一个任务 → 独立 session_id, 与机器人那条**不同**。

    形如 ``feishu-<open_id>-web-<hex12>``。为什么它一定不会被 ``route`` 误认成规范 id:
    ``bot_session_id`` 把私聊 open_id 里的 ``-`` 转义成 ``_``, 所以私聊规范 id 只含一个
    ``-``; 群聊那支形如 ``feishu-chat-<chat_id>``, 其 ``chat`` 段固定。本函数在规范 id
    之后再接 ``-web-<hex>``, 于是两边的像不相交 (``_WEB_SESSION_RE`` 是这句话的可执行版)。

    这不是美观问题: 若某个子会话恰好长得像规范 id, ``route`` 的 adopt 分支会把它当成机器人
    会话接管 —— 机器人从此在用户的某个网页任务里说话, 而那个任务的历史又会被当成私聊历史。
    故返回前用 ``_WEB_SESSION_RE`` 再验一次, 派生规则被改动时宁可 500 也不静默放过。
    """
    sid = f"{bot_session_id(open_id)}-{_WEB_INFIX}-{secrets.token_hex(_WEB_SUFFIX_BYTES)}"
    if not is_web_session_id(sid):
        raise AssertionError(f"derived web session id {sid!r} is not recognizable as one")
    return sid


def is_web_session_id(session_id: str) -> bool:
    """该 id 是网页应用建的子会话吗 —— 与 ``web_session_id`` 共用同一条格式定义。"""
    return bool(_WEB_SESSION_RE.match(session_id))


@dataclass
class FeishuRoute:
    """一条路由记录。群聊只有 ``chat_id``, 私聊只有 ``open_id``, 另一个留空。"""

    open_id: str
    session_id: str
    chat_id: str = ""


@dataclass
class FeishuManager:
    """按 open_id 幂等地把飞书用户路由到各自的 Session。

    ``_ai_id`` / ``_workspace_root`` 是缺省值, 单次 ``route`` 可覆盖。``_ai_id`` 为空或
    指向一个没起来的 AI 时, ``_resolve_ai`` 会回落到任一活着的 AI (见那里的原因)。``_routes`` 是内存态
    (路由键 → session_id); 因 session_id 由路由键确定性派生, 重启后经 ``route`` 的 adopt
    分支自愈, 无需额外持久化。
    """

    _sm: SessionManager
    _ai_id: str = ""
    _workspace_root: str = ""
    _routes: dict[str, str] = field(default_factory=dict)
    _lock: anyio.Lock = field(default_factory=anyio.Lock)

    def _session_id(self, key: str) -> str:
        """派生确定性 session_id, 加 ``feishu-`` 前缀与 SPA 手建 session 命名空间隔离。

        群聊键 ``chat:<chat_id>`` → ``feishu-chat-<chat_id>``; 私聊 → ``feishu-<open_id>``。
        私聊侧把 ``-`` 转义成 ``_``, 否则某人 open_id 恰为 ``chat-oc_x`` 时会与群 ``oc_x`` 撞成
        同一个 session (陌生人共享上下文的隐私事故)。飞书真实 open_id 不含 ``-``, 这只是防御层。
        """
        if key.startswith("chat:"):
            return f"feishu-chat-{_sanitize_open_id(key.removeprefix('chat:'))}"
        return bot_session_id(key)

    def _workspace_for(self, key: str) -> str:
        """每个路由键得到独立子目录 (root 空则以 cwd 为父)。

        群聊 → ``<root>/chat-<chat_id>``, 私聊 → ``<root>/<open_id>`` (``-`` 同样转义,
        与 ``_session_id`` 一致, 免得两个键指到同一个 workspace 目录)。
        """
        root = self._workspace_root or os.getcwd()
        if key.startswith("chat:"):
            return os.path.join(root, f"chat-{_sanitize_open_id(key.removeprefix('chat:'))}")
        return os.path.join(root, _sanitize_open_id(key).replace("-", "_"))

    def _resolve_ai(self, ai_id: str | None) -> str:
        """本次路由该挂哪个 AI: 显式 > ``--feishu-ai-id`` > **任一活着的 AI**。

        最后那级兜底是刻意加的, 因为前两级在装了包的用户那里**双双为空**: launcher
        (``inno-setup/haitun.c``) 只传 ``--default-agent`` / ``--default-workspace``,
        从不传 ``--feishu-ai-id``; 而 SPA 建 AI 时用的是随机 uuid, 谁也猜不到。
        于是配置里那个 id 永远不存在, ``_rebind_if_backend_gone`` 就永远换不到活 AI,
        飞书用户**永久**收到一句「AI 后端未运行」——重启网关也治不好, 因为坏掉的
        ``backend_id`` 跟着 Session 一起被持久化了。

        为什么兜底而不是报错: 用户在 SPA 里明明有个能用的 AI, 机器人却因为一个他没
        设过的 CLI 参数而装死, 这不是「配置缺失」该有的表现。挑 AI 只是**选一个能用的
        后端**, 不涉及凭证或权限 —— 反正同一个 Gateway 进程里的 AI 都是这台机器的主人
        自己建的。仍然一个都没有时才回到报错 (``route`` 抛 ValueError → 400)。
        """
        explicit = (ai_id or "").strip()
        if explicit:
            return explicit
        if self._ai_id and self._sm.backend_alive_id("ai", self._ai_id):
            return self._ai_id
        fallback = self._sm.first_live_ai_id()
        if fallback:
            # 配了但没起来 (打错字 / AI 建失败) 与压根没配, 是两件该分开看的事。
            if self._ai_id:
                logger.warning(
                    f"FeishuManager: configured ai_id {self._ai_id!r} is not running; "
                    f"falling back to live AI {fallback!r}"
                )
            else:
                logger.info(f"FeishuManager: no --feishu-ai-id configured; using live AI {fallback!r}")
            return fallback
        # 一个 AI 都没有: 保留配置值 (可能为空), 让调用方按原样处理。
        return self._ai_id

    async def _rebind_if_backend_gone(self, session_id: str, resolved_ai: str) -> bool:
        """该 Session 还能用吗 —— 不能且有救时, 拆掉它让调用方重建。

        返回 ``True`` = 直接复用; ``False`` = 已删除, 请按 *resolved_ai* 重建。

        为什么需要这一步: Session 的上游地址由 backend **id** 推导 (见
        ``SessionManager.backend_alive``), 所以「AI 被删了 / 重启时 AI 恢复失败」不会让
        Session 消失, 只会让它握着一个没人监听的 pipe。route 的 cache/adopt 两支原先无条件
        把这个 socket 交回去, 于是那个飞书用户**永久**收到一句
        ``Cannot connect to host localhost:80`` —— 重启网关也治不好, 因为坏掉的
        ``backend_id`` 跟着 Session 一起被持久化了。

        只在**换得到**活着的 AI 时才拆: 若 *resolved_ai* 本身也不存在, 重建只会得到同样坏的
        Session, 那就留着它, 让 ``AiClient`` 那条写明 socket 的错误浮上来 (可读得多)。
        """
        if self._sm.backend_alive(session_id):
            return True
        if not resolved_ai or not self._sm.backend_alive_id("ai", resolved_ai):
            logger.warning(
                f"FeishuManager: session {session_id!r} has a dead backend "
                f"{self._sm.get_backend_id(session_id)!r} and no live AI to rebind onto "
                f"(resolved_ai={resolved_ai!r}); keeping it so the error names the socket"
            )
            return True
        logger.warning(
            f"FeishuManager: session {session_id!r} backend "
            f"{self._sm.get_backend_id(session_id)!r} is gone; rebuilding on {resolved_ai!r}"
        )
        await self._sm.delete(session_id)
        return False

    async def route(
        self,
        open_id: str,
        *,
        chat_id: str = "",
        chat_type: str = "",
        ai_id: str | None = None,
        workspace: str | None = None,
    ) -> tuple[str, str]:
        """幂等地拿到该会话对应 Session 的 (channel_socket, session_id)。

        群聊 (``chat_type`` 为 group/topic 且 ``chat_id`` 非空) 按 ``chat_id`` 路由——整群
        共用一个 Session; 其余按发送者 ``open_id`` 路由。首次见到某键时按需 spawn 一个
        Session; 之后命中缓存或 adopt 已存在 Session。挂哪个 AI 见 ``_resolve_ai``
        (显式 > ``--feishu-ai-id`` > 任一活着的 AI); 一个 AI 都没有时抛 ``ValueError``
        (由 handler 转 400); 私聊而 ``open_id`` 为空时同样抛 ``ValueError`` (群聊不要求)。
        """
        key = route_key(open_id, chat_id, chat_type)
        if not key:
            raise ValueError("open_id must not be empty")
        sid = self._session_id(key)
        resolved_ai = self._resolve_ai(ai_id)
        async with self._lock:
            logger.debug(f"FeishuManager: acquired lock for route {key!r}")
            # 命中路由表且 Session 仍活 → 直接复用。
            cached = self._routes.get(key)
            if cached is not None and self._sm.has(cached):
                if await self._rebind_if_backend_gone(cached, resolved_ai):
                    return self._sm.get_socket(cached), cached
                del self._routes[key]

            # 路由表未命中但 Session 已存在 (重启后被 state 恢复, 或 SPA 侧同名建过) → adopt。
            if self._sm.has(sid):
                if await self._rebind_if_backend_gone(sid, resolved_ai):
                    self._routes[key] = sid
                    logger.debug(f"FeishuManager: adopted existing session {sid!r} for {key!r}")
                    return self._sm.get_socket(sid), sid

            if not resolved_ai:
                raise ValueError("no ai_id: set Gateway --feishu-ai-id or pass ai_id in the request")
            ws = workspace or self._workspace_for(key)
            await anyio.Path(ws).mkdir(parents=True, exist_ok=True)

            try:
                # agent omitted → SessionManager applies Gateway --default-agent
                info = await self._sm.create(ai_id=resolved_ai, id=sid, workspace=ws)
                socket = info.channel_socket
            except ValueError as e:
                # 并发竞态: 另一路已抢先建同名 session (锁内理论不会, 防御性兜底)。
                if "already exists" not in str(e):
                    raise
                logger.debug(f"FeishuManager: session {sid!r} raced, fetching socket")
                socket = self._sm.get_socket(sid)

            self._routes[key] = sid
            logger.info(f"FeishuManager: routed {key!r} -> session {sid!r} (workspace={ws!r})")
            return socket, sid

    def list_routes(self) -> list[FeishuRoute]:
        """列出所有路由。群聊记录填 ``chat_id`` 留空 ``open_id``, 私聊反之。"""
        out: list[FeishuRoute] = []
        for key, sid in self._routes.items():
            if key.startswith("chat:"):
                out.append(FeishuRoute(open_id="", chat_id=key.removeprefix("chat:"), session_id=sid))
            else:
                out.append(FeishuRoute(open_id=key, chat_id="", session_id=sid))
        return out
