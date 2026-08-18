from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import anyio
from loguru import logger

from psi_agent.gateway._ai_manager import AIManager
from psi_agent.gateway._defaults import ensure_workspace_dir
from psi_agent.gateway._manager import (
    _ensure_socket_dir,
    _new_uuid,
    _noop,
    _remove_socket,
    _socket_path,
    _wait_socket,
)
from psi_agent.gateway._router_manager import RouterManager
from psi_agent.session import Session
from psi_agent.session.schedule_registry import ACTIVATE_ALL


@dataclass
class SessionInfo:
    id: str
    backend_type: str
    backend_id: str
    workspace: str
    """User workspace (open folder). Relative file IO / project files live here."""

    channel_socket: str
    # Step 2: surfaced to REST / state. Empty → Session treats agent ≡ workspace.
    agent: str = ""
    """Agent package path (tools/system). Empty → single-root compat."""

    active_schedules: tuple[str, ...] = ()
    """Schedule names this Session activates (i.e. actually fires); ``("*",)`` = all.

    Activation is a property of **(session x schedule)**: every Session on a
    workspace reads every entry, but each fires only the ones in its own list.
    ``SchedulerManager`` keeps exactly one fully activated (``("*",)``) scheduler
    Session per workspace, and that Session is **entirely hidden** from the SPA
    and from ``state/latest.json`` (filtered out of ``list_all`` by default,
    skipped when persisting) — 刻意为之: it is not a user session, and listing it
    would only invite someone to delete it.
    """

    deactive_schedules: tuple[str, ...] = ()
    """Schedule names excluded from ``active_schedules`` (blacklist, wins over it).

    A wildcard whitelist plus a blacklist is the only way to say "all of these
    except a few": a whitelist is an enumeration and cannot cover a ``TASK.md``
    created after startup, whereas the wildcard does, with the blacklist carving
    out the entries assigned elsewhere.
    """

    @property
    def scheduler(self) -> bool:
        """Whether this Session is the workspace's fully activated scheduler.

        Used for ``list_all`` filtering and REST display; the authoritative
        ownership information lives in ``active_schedules``.
        """
        return ACTIVATE_ALL in self.active_schedules

    @property
    def ai_id(self) -> str:
        """Compatibility alias for clients that still create direct-AI sessions."""
        return self.backend_id


@dataclass
class _SessionEntry:
    scope: anyio.CancelScope
    info: SessionInfo


@dataclass
class SessionManager:
    _aim: AIManager
    _prefix: str
    _tg: Any  # anyio.TaskGroup (ty不识别的第三方类型)
    _rm: RouterManager | None = None
    _entries: dict[str, _SessionEntry] = field(default_factory=dict)
    _lock: anyio.Lock = field(default_factory=anyio.Lock)
    # Separate from _lock: rebind spans delete + create, each of which takes
    # _lock itself, so it cannot hold _lock for the whole operation.
    _rebind_lock: anyio.Lock = field(default_factory=anyio.Lock)
    _persist: Callable[[], Awaitable[None]] = _noop
    # Injected by Gateway.run from --default-agent / --default-workspace / --appdata.
    _default_agent: str = ""
    _default_workspace: str = ""
    _appdata: str = ""

    async def create(
        self,
        backend_type: str = "ai",
        backend_id: str = "",
        *,
        ai_id: str = "",
        id: str = "",
        workspace: str = "",
        agent: str = "",
        active_schedules: tuple[str, ...] = (),
        deactive_schedules: tuple[str, ...] = (),
    ) -> SessionInfo:
        """Spawn a Session.

        Step 2 wiring: *agent* / *workspace* fall back to Gateway defaults when
        omitted. ``Session(agent=…)`` (from #472) then loads the capability pack
        from that directory. Tools that resolve relative paths via ContextVar
        are a later PR — this only passes the path in.

        *active_schedules* / *deactive_schedules* name, per entry, which schedules
        this Session fires (``("*",)`` = all; empty by default = none, with the
        blacklist subtracting first). The fully activated Session is created by
        ``SchedulerManager``, deduplicated per workspace and hidden from SPA /
        state. Ordinary callers pass neither argument.
        """
        session_id = id or _new_uuid()
        workspace = workspace.strip() or self._default_workspace or os.getcwd()
        # Intentional: GET /defaults only announces the path; mkdir here at
        # Session create / start-chat so Haitun open does not leave an empty
        # Desktop folder.
        workspace = await ensure_workspace_dir(workspace)
        agent = agent.strip() or self._default_agent
        backend_id = backend_id or ai_id
        upstream_socket = self.resolve_backend_socket(backend_type, backend_id)
        async with self._lock:
            logger.debug(f"SessionManager: acquired lock for create {session_id!r}")
            if session_id in self._entries:
                raise ValueError(f"Session {session_id!r} already exists")
            channel_socket = _socket_path(self._prefix, "channels", session_id)
            await _ensure_socket_dir(channel_socket)
            # Hand paths to Session (#472 / #4C). Empty agent → Session uses workspace.
            sess = Session(
                workspace=workspace,
                agent=agent,
                appdata=self._appdata,
                channel_socket=channel_socket,
                ai_socket=upstream_socket,
                session_id=session_id,
                active_schedules=",".join(active_schedules),
                deactive_schedules=",".join(deactive_schedules),
            )
            scope = anyio.CancelScope()

            async def _run_session() -> None:
                try:
                    with scope:
                        await sess.run()
                except Exception as e:
                    logger.error(f"Session {session_id!r} crashed: {e!r}")
                    async with self._lock:
                        self._entries.pop(session_id, None)
                    await self._persist()

            logger.debug(f"SessionManager: starting session {session_id!r} task")
            self._tg.start_soon(_run_session)
            info = SessionInfo(
                id=session_id,
                backend_type=backend_type,
                backend_id=backend_id,
                workspace=workspace,
                channel_socket=channel_socket,
                agent=agent,
                active_schedules=active_schedules,
                deactive_schedules=deactive_schedules,
            )
            self._entries[session_id] = _SessionEntry(scope=scope, info=info)
        try:
            await _wait_socket(info.channel_socket)
        except Exception:
            logger.warning(f"Session {session_id!r} did not become ready, rolling back")
            with anyio.CancelScope(shield=True):
                async with self._lock:
                    self._entries.pop(session_id, None)
                    scope.cancel()
                    await _remove_socket(info.channel_socket)
                await self._persist()
            raise
        await self._persist()
        logger.info(
            f"Session {session_id!r} created on {info.channel_socket} "
            f"-> {backend_type} {backend_id!r} agent={agent!r} workspace={workspace!r}"
        )
        return info

    def resolve_backend_socket(self, backend_type: str, backend_id: str) -> str:
        if backend_type == "ai":
            return self._aim.get_socket(backend_id)
        if backend_type == "router":
            if self._rm is None:
                raise LookupError("Router manager is not configured")
            return self._rm.get_socket(backend_id)
        raise ValueError("backend_type must be either 'ai' or 'router'")

    def backend_alive_id(self, backend_type: str, backend_id: str) -> bool:
        """Is *backend_id* of *backend_type* currently running?

        The by-id twin of ``backend_alive``: callers about to (re)create a Session
        use this to check the backend they are *aiming at*, before committing.
        """
        if not backend_id:
            return False
        if backend_type == "ai":
            return self._aim.has(backend_id)
        if backend_type == "router":
            return self._rm is not None and self._rm.has(backend_id)
        return False

    def first_live_ai_id(self) -> str:
        """Id of some currently running AI, or ``""`` when none run.

        A last-resort fallback for callers that must attach a Session to *an* AI
        but whose configured default is missing. Only AIs are offered: a Router
        needs upstreams configured deliberately, so guessing one is wrong.
        """
        return self._aim.first_live_id()

    def resolve_restore_backend(self, backend_type: str, backend_id: str) -> tuple[str, str]:
        """Backend a *restored* Session should actually attach to.

        Returns the pair unchanged when that backend is live. When it is not,
        falls back to any live AI: a snapshot can name a backend that no longer
        exists, because AI ids are fresh uuids per Gateway run and a snapshot
        written while no AI was live still carries the Session's old binding.
        Restoring such a binding verbatim yields a Session whose socket path is
        well-formed but has nobody listening, and the breakage only surfaces at
        message time as "AI 后端未运行" (see ``backend_alive``).

        Restore only. A caller creating a *fresh* Session names its backend
        deliberately and keeps it even when dead (see
        ``test_sessionmanager_create_without_ai``). When nothing is live the
        original pair is returned — there is nothing better to offer, and
        restore must still succeed so the Session reappears in the SPA.
        """
        if self.backend_alive_id(backend_type, backend_id):
            return backend_type, backend_id
        fallback = self.first_live_ai_id()
        if not fallback:
            return backend_type, backend_id
        logger.warning(
            f"Restore: backend {backend_type} {backend_id!r} is not running, rebinding to live AI {fallback!r}"
        )
        return "ai", fallback

    async def ensure_live_backend(self, session_id: str) -> str:
        """Rebind *session_id* onto a live AI when its own backend is gone.

        Returns the channel socket to stream from — the existing one when the
        backend is healthy (the overwhelmingly common path, one dict lookup).

        ``resolve_restore_backend`` only runs at Gateway startup, but a backend
        can die *after* that: the AI is deleted and recreated from the SPA, which
        mints a fresh uuid, and every Session still names the old one. Nothing
        then repairs the binding until the next restart, so every message fails
        with "AI 后端未运行" while a perfectly good AI sits unreferenced.

        ``Session`` reads ``ai_socket`` once, when ``SessionAgent.create`` builds
        its ``AiClient``, so the socket cannot be swapped on a running Session —
        the rebind has to delete and recreate it under the same id. That keeps
        the id, workspace, agent, and channel-socket path stable, so SPA links
        and history (keyed by session id) survive; only the in-flight process is
        replaced. Conversation history lives in AppData keyed by session id, so
        it is untouched.
        """
        async with self._rebind_lock:
            if session_id not in self._entries:
                raise LookupError(f"Session {session_id!r} not found")
            info = self._entries[session_id].info
            if self.backend_alive_id(info.backend_type, info.backend_id):
                return info.channel_socket
            fallback = self.first_live_ai_id()
            if not fallback:
                # Nothing to rebind onto. Leave the Session as-is and let the
                # stream surface the real "backend not running" error rather
                # than a rebind failure that hides it.
                logger.warning(
                    f"Session {session_id!r} backend {info.backend_id!r} is not running and no live AI exists"
                )
                return info.channel_socket
            logger.warning(
                f"Session {session_id!r} backend {info.backend_type} {info.backend_id!r} is not running, "
                f"rebinding to live AI {fallback!r}"
            )
            await self.delete(session_id)
            revived = await self.create(
                backend_type="ai",
                backend_id=fallback,
                workspace=info.workspace,
                agent=info.agent,
                id=session_id,
                active_schedules=info.active_schedules,
                deactive_schedules=info.deactive_schedules,
            )
            return revived.channel_socket

    def backend_alive(self, session_id: str) -> bool:
        """Is the backend this Session streams from actually running?

        A Session may legitimately outlive its backend: ``AIManager.get_socket``
        derives the pipe/socket path from the **id**, so a Session created before
        its AI (restore ordering) or after the AI was deleted still holds a
        well-formed address — it simply has nobody listening. Creation therefore
        cannot reject it (see ``test_sessionmanager_create_without_ai``), and the
        breakage only shows up at message time, deep inside aiohttp.

        This is the cheap check that lets callers notice *before* streaming.
        Unknown ``backend_type`` counts as dead rather than raising: callers use
        this to decide whether to rebuild, and a Session with an unroutable
        backend is exactly what they should rebuild.
        """
        if session_id not in self._entries:
            raise LookupError(f"Session {session_id!r} not found")
        info = self._entries[session_id].info
        if info.backend_type == "ai":
            return self._aim.has(info.backend_id)
        if info.backend_type == "router":
            return self._rm is not None and self._rm.has(info.backend_id)
        return False

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            logger.debug(f"SessionManager: acquired lock for delete {session_id!r}")
            if session_id not in self._entries:
                raise LookupError(f"Session {session_id!r} not found")
            entry = self._entries.pop(session_id)
            entry.scope.cancel()
            await _remove_socket(entry.info.channel_socket)
        await self._persist()
        logger.info(f"Session {session_id!r} deleted")

    async def list_all(self, *, include_scheduler: bool = False) -> list[SessionInfo]:
        """List the user sessions.

        Scheduler Sessions are **not** included by default (刻意为之: they are not
        user sessions, and listing them in the SPA only invites deletion). Pass
        ``include_scheduler=True`` for operational or internal dedup use.
        """
        infos = [e.info for e in list(self._entries.values())]
        if include_scheduler:
            return infos
        return [info for info in infos if not info.scheduler]

    def get_socket(self, session_id: str) -> str:
        if session_id not in self._entries:
            raise LookupError(f"Session {session_id!r} not found")
        return self._entries[session_id].info.channel_socket

    def has(self, session_id: str) -> bool:
        return session_id in self._entries

    def get_workspace(self, session_id: str) -> str:
        if session_id not in self._entries:
            raise LookupError(f"Session {session_id!r} not found")
        return self._entries[session_id].info.workspace

    def get_agent(self, session_id: str) -> str:
        if session_id not in self._entries:
            raise LookupError(f"Session {session_id!r} not found")
        return self._entries[session_id].info.agent

    def get_backend_id(self, session_id: str) -> str:
        """Backend id the session is attached to — needed when a scheduler Session reuses the same AI instance."""
        if session_id not in self._entries:
            raise LookupError(f"Session {session_id!r} not found")
        return self._entries[session_id].info.backend_id
