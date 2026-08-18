from __future__ import annotations

import os

import anyio
import pytest

from psi_agent.gateway._ai_manager import AIManager
from psi_agent.gateway._feishu_manager import (
    FeishuManager,
    _sanitize_open_id,
    bot_session_id,
    is_web_session_id,
    web_session_id,
)
from psi_agent.gateway._session_manager import SessionManager


async def _make_managers(tg: object) -> tuple[AIManager, SessionManager]:
    am = AIManager(_prefix="gw-test", _tg=tg)
    sm = SessionManager(_aim=am, _prefix="gw-test", _tg=tg)
    await am.create(provider="o", model="m", api_key="k", base_url="b", id="ai1")
    return am, sm


async def _drain(sm: SessionManager, am: AIManager) -> None:
    """删掉所有 spawn 出来的 Session/AI 常驻任务, 使 tg.__aexit__ 能干净退出。

    与 test_manager.py 一致——显式 delete 而非 cancel task-group scope。
    """
    for info in await sm.list_all():
        await sm.delete(info.id)
    for info in await am.list_all():
        await am.delete(info.id)


def test_sanitize_open_id() -> None:
    assert _sanitize_open_id("ou_abc123") == "ou_abc123"
    assert _sanitize_open_id("a/b c:d") == "a_b_c_d"


def test_bot_session_id_matches_what_route_derives() -> None:
    """网页应用要在**不** spawn 的前提下认出机器人那张卡, 故两处派生必须一致。"""
    assert bot_session_id("ou_alice") == "feishu-ou_alice"
    fm = FeishuManager(_sm=None)  # type: ignore[arg-type]
    assert fm._session_id("ou_alice") == bot_session_id("ou_alice")


def test_web_session_id_is_unique_per_call() -> None:
    """同一个人在工作台里点两次「新建任务」必须得到两条独立会话。"""
    first = web_session_id("ou_alice")
    second = web_session_id("ou_alice")
    assert first != second
    assert first.startswith("feishu-ou_alice-web-")


@pytest.mark.parametrize(
    "open_id",
    [
        "ou_alice",
        # open_id 里带 ``-``: ``bot_session_id`` 会把它转义成 ``_``, 中段因此仍无 ``-``。
        "chat-oc_team",
        # 净化层要兜住的意外字符。
        "a/b c:d",
    ],
)
def test_web_session_id_is_never_mistaken_for_a_canonical_id(open_id: str) -> None:
    """核心隔离不变量: 子会话 id 落不进任何路由键派生出的像里。

    若它能被认成规范 id, ``route`` 的 adopt 分支会把它当成机器人会话接管 —— 机器人从此在
    用户的某个网页任务里说话, 而该任务的历史又会被当成私聊历史。
    """
    sid = web_session_id(open_id)
    fm = FeishuManager(_sm=None)  # type: ignore[arg-type]
    assert is_web_session_id(sid)
    # 私聊那支: 任何 open_id 都不可能派生出这个 id。
    assert fm._session_id(sid) != sid
    assert sid != bot_session_id(open_id)
    # 群聊那支: ``feishu-chat-<chat_id>`` 同样够不到。
    assert fm._session_id(f"chat:{sid}") != sid


def test_group_lookalike_is_not_taken_for_a_web_session() -> None:
    """``chat_id`` 允许带 ``-``, 所以 ``feishu-chat-oc-web-<hex>`` 这种像必须被排除。

    否则页面会把一个**群会话**当成自己建的子会话, 反过来 ``route`` 也可能 adopt 子会话。
    """
    fm = FeishuManager(_sm=None)  # type: ignore[arg-type]
    lookalike = fm._session_id("chat:oc-web-0123456789ab")
    assert lookalike == "feishu-chat-oc-web-0123456789ab"
    assert not is_web_session_id(lookalike)


@pytest.mark.parametrize(
    "session_id",
    [
        "feishu-ou_alice",  # 机器人私聊卡
        "feishu-chat-oc_team",  # 群会话
        "feishu-ou_alice-web-",  # 缺随机尾巴
        "feishu-ou_alice-web-XYZ123456789",  # 非十六进制
        "feishu-ou_alice-web-0123456789",  # 长度不足
        "spa-built-session",  # SPA 手建
        "",
    ],
)
def test_is_web_session_id_rejects_everything_else(session_id: str) -> None:
    assert not is_web_session_id(session_id)


@pytest.mark.anyio
async def test_route_spawns_and_is_idempotent(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        socket1, sid1 = await fm.route("ou_alice")
        assert sid1 == "feishu-ou_alice"
        assert sm.has(sid1)

        # 二次幂等: 同 open_id 拿回同 socket/session_id, 不再新建。
        socket2, sid2 = await fm.route("ou_alice")
        assert (socket2, sid2) == (socket1, sid1)
        assert len(await sm.list_all()) == 1

        # 不同 open_id → 独立 session。
        _, sid_bob = await fm.route("ou_bob")
        assert sid_bob == "feishu-ou_bob"
        assert len(await sm.list_all()) == 2
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_creates_per_user_workspace(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        await fm.route("ou_alice")
        expected = os.path.join(str(tmp_path), "ou_alice")
        assert await anyio.Path(expected).is_dir()
        assert sm.get_workspace("feishu-ou_alice") == expected
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_request_ai_id_and_workspace_override(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        await am.create(provider="o", model="m", api_key="k", base_url="b", id="ai2")
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        custom_ws = os.path.join(str(tmp_path), "custom")
        _, sid = await fm.route("ou_alice", ai_id="ai2", workspace=custom_ws)
        assert sm.get_workspace(sid) == custom_ws
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_no_ai_id_raises(tmp_path: str) -> None:
    """一个 AI 都没有时才 400 —— 有活着的 AI 就该回落到它 (见下面几条)。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am = AIManager(_prefix="gw-test", _tg=tg)
        sm = SessionManager(_aim=am, _prefix="gw-test", _tg=tg)
        fm = FeishuManager(_sm=sm, _ai_id="", _workspace_root=str(tmp_path))
        with pytest.raises(ValueError, match="no ai_id"):
            await fm.route("ou_alice")
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_without_configured_ai_id_uses_a_live_ai(tmp_path: str) -> None:
    """装了包的用户就是这个状态: launcher 不传 ``--feishu-ai-id``, AI 由 SPA 用随机 uuid 建。

    在此之前这里会 400 / 永久「AI 后端未运行」: 配置里的 id 为空, 谁也猜不到那个 uuid。
    """
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice")
        assert sm.get_backend_id(sid) == "ai1"
        assert sm.backend_alive(sid)
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_falls_back_when_configured_ai_id_is_not_running(tmp_path: str) -> None:
    """``--feishu-ai-id`` 指向一个没建起来的 AI (打错字 / 建失败) 也不该让机器人装死。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="feishu-default", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice")
        assert sm.get_backend_id(sid) == "ai1"
        assert sm.backend_alive(sid)
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_prefers_the_configured_ai_when_it_is_alive(tmp_path: str) -> None:
    """回落只在配置项不可用时生效; 配了又活着就必须用配的那个。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        await am.create(provider="o", model="m", api_key="k2", base_url="b", id="feishu-default")
        fm = FeishuManager(_sm=sm, _ai_id="feishu-default", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice")
        assert sm.get_backend_id(sid) == "feishu-default"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_rebinds_a_restored_session_onto_a_live_ai(tmp_path: str) -> None:
    """本次修复的完整回归: 重启后被 state 恢复的 Session 握着一个死 backend_id。

    ``AIManager.get_socket`` 由 **id** 推路径, 所以恢复不会失败, 只会得到一个没人监听的
    管道; 从前 adopt 分支无条件把它交回去, 那个飞书用户于是**永久**收到「AI 后端未运行」,
    重启也治不好 —— 坏 id 跟着 Session 一起被持久化。
    """
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        # 等价于 state 恢复: session 指向一个并不存在的 AI。
        await sm.create(ai_id="feishu-default", id="feishu-ou_alice", workspace=str(tmp_path))
        assert not sm.backend_alive("feishu-ou_alice")

        fm = FeishuManager(_sm=sm, _ai_id="", _workspace_root=str(tmp_path))
        _, sid = await fm.route("ou_alice")

        assert sid == "feishu-ou_alice"
        assert sm.get_backend_id(sid) == "ai1"
        assert sm.backend_alive(sid)
        assert len(await sm.list_all()) == 1
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_keeps_a_dead_session_when_there_is_nothing_to_rebind_onto(tmp_path: str) -> None:
    """没有任何活 AI 时保留坏 Session: 重建只会得到同样坏的一个。

    此时让 ``AiClient`` 那条**写明 socket** 的错误浮上来, 比静默换一个还是连不上的
    session 有用得多。
    """
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am = AIManager(_prefix="gw-test", _tg=tg)
        sm = SessionManager(_aim=am, _prefix="gw-test", _tg=tg)
        info = await sm.create(ai_id="feishu-default", id="feishu-ou_alice", workspace=str(tmp_path))

        fm = FeishuManager(_sm=sm, _ai_id="feishu-default", _workspace_root=str(tmp_path))
        socket, sid = await fm.route("ou_alice")

        assert (socket, sid) == (info.channel_socket, "feishu-ou_alice")
        assert sm.get_backend_id(sid) == "feishu-default"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_explicit_ai_id_beats_the_fallback(tmp_path: str) -> None:
    """请求体里的 ``ai_id`` 仍是最高优先级, 回落不能把它盖掉。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice", ai_id="ai-explicit")
        assert sm.get_backend_id(sid) == "ai-explicit"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_empty_open_id_raises(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))
        with pytest.raises(ValueError, match="open_id"):
            await fm.route("")
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_list_routes(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))
        await fm.route("ou_alice")
        await fm.route("ou_bob")

        routes = fm.list_routes()
        pairs = {(r.open_id, r.session_id) for r in routes}
        assert pairs == {("ou_alice", "feishu-ou_alice"), ("ou_bob", "feishu-ou_bob")}
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_group_chat_keys_on_chat_id(tmp_path: str) -> None:
    """群聊按 chat_id 建 session, 同群不同发送者共用一个 session。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        socket1, sid1 = await fm.route("ou_alice", chat_id="oc_team", chat_type="group")
        assert sid1 == "feishu-chat-oc_team"

        # 同群另一个人 → 同一 session, 不新建。
        socket2, sid2 = await fm.route("ou_bob", chat_id="oc_team", chat_type="group")
        assert (socket2, sid2) == (socket1, sid1)
        assert len(await sm.list_all()) == 1

        # 另一个群 → 独立 session。
        _, sid_other = await fm.route("ou_alice", chat_id="oc_other", chat_type="group")
        assert sid_other == "feishu-chat-oc_other"
        assert len(await sm.list_all()) == 2
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_p2p_still_keys_on_open_id(tmp_path: str) -> None:
    """私聊 (含带 chat_id 的 p2p) 仍按发送者 open_id 建 session。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice", chat_id="oc_dm", chat_type="p2p")
        assert sid == "feishu-ou_alice"

        # 同一人的私聊与其所在群互不干扰。
        _, sid_group = await fm.route("ou_alice", chat_id="oc_team", chat_type="group")
        assert sid_group == "feishu-chat-oc_team"
        assert len(await sm.list_all()) == 2
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_group_creates_per_chat_workspace(tmp_path: str) -> None:
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        await fm.route("ou_alice", chat_id="oc_team", chat_type="group")
        expected = os.path.join(str(tmp_path), "chat-oc_team")
        assert await anyio.Path(expected).is_dir()
        assert sm.get_workspace("feishu-chat-oc_team") == expected
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_group_without_chat_id_falls_back_to_open_id(tmp_path: str) -> None:
    """chat_type=group 但 chat_id 缺失 → 退回按 open_id, 不炸也不建空名 session。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice", chat_id="", chat_type="group")
        assert sid == "feishu-ou_alice"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_group_empty_open_id_allowed(tmp_path: str) -> None:
    """群聊路由键是 chat_id, 故 open_id 缺失也应能路由 (不再强制非空)。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        _, sid = await fm.route("", chat_id="oc_team", chat_type="group")
        assert sid == "feishu-chat-oc_team"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_topic_chat_keys_on_chat_id(tmp_path: str) -> None:
    """话题群 (chat_type=topic) 与 group 同样按 chat_id 建 session。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        _, sid = await fm.route("ou_alice", chat_id="oc_topic", chat_type="topic")
        assert sid == "feishu-chat-oc_topic"
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_list_routes_reports_group_key(tmp_path: str) -> None:
    """群 session 在路由表里以 chat_id 为键, open_id 留空 (群不属于某个人)。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))
        await fm.route("ou_alice")
        await fm.route("ou_bob", chat_id="oc_team", chat_type="group")

        entries = {(r.open_id, r.chat_id, r.session_id) for r in fm.list_routes()}
        assert entries == {
            ("ou_alice", "", "feishu-ou_alice"),
            ("", "oc_team", "feishu-chat-oc_team"),
        }
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_adopts_existing_group_session(tmp_path: str) -> None:
    """重启后群 session 已被 state 恢复 → adopt 不重建。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        info = await sm.create(ai_id="ai1", id="feishu-chat-oc_team", workspace=str(tmp_path))

        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))
        socket, sid = await fm.route("ou_alice", chat_id="oc_team", chat_type="group")
        assert (socket, sid) == (info.channel_socket, "feishu-chat-oc_team")
        assert len(await sm.list_all()) == 1
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_group_and_lookalike_open_id_do_not_collide(tmp_path: str) -> None:
    """私聊 open_id 恰好长得像群前缀 (``chat-oc_team``) 时, 不能撞进群 ``oc_team`` 的 session。

    群 session_id 是 ``feishu-chat-<chat_id>``, 若私聊直接拼 ``feishu-<open_id>`` 则二者会
    撞成同名 —— 两个陌生人共享上下文, 是隐私事故, 故私聊侧须把 ``-`` 转义掉。
    """
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))

        _, group_sid = await fm.route("ou_alice", chat_id="oc_team", chat_type="group")
        _, dm_sid = await fm.route("chat-oc_team", chat_id="oc_dm", chat_type="p2p")

        assert group_sid != dm_sid
        assert sm.get_workspace(group_sid) != sm.get_workspace(dm_sid)
        assert len(await sm.list_all()) == 2
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_route_adopts_existing_session(tmp_path: str) -> None:
    """模拟重启: session 已存在 (被 state 恢复), route 直接 adopt 不重建。"""
    tg = anyio.create_task_group()
    await tg.__aenter__()
    try:
        am, sm = await _make_managers(tg)
        # 预先手建一个同名 session (等价于 state 恢复后的场景)。
        info = await sm.create(ai_id="ai1", id="feishu-ou_alice", workspace=str(tmp_path))

        fm = FeishuManager(_sm=sm, _ai_id="ai1", _workspace_root=str(tmp_path))
        socket, sid = await fm.route("ou_alice")
        assert sid == "feishu-ou_alice"
        assert socket == info.channel_socket
        assert len(await sm.list_all()) == 1  # 未重建
    finally:
        await _drain(sm, am)
        await tg.__aexit__(None, None, None)
