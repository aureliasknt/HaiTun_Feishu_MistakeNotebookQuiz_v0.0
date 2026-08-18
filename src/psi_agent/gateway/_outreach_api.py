"""场景 3 的理解确认卡在飞书网页应用里的读写入口。

场景 3 的问答由**机器人私聊**那一轮完成 (模型按 ``outreach-confirmation-card`` 技能作答,
再用 ``outreach_confirm_card`` 发卡)。本模块只负责让工作台也能看到并答完那张卡, 因此只有
两件事:

* ``GET  /outreach/card``   —— 读 ``outreach/state.yaml`` 里待确认的 ``last_qa``, 供页面渲染。
* ``POST /outreach/answer`` —— 用 ``outreach_confirm_handle`` 的同一批 helper 落库。

这里**没有**提问入口。曾经有一个 ``POST /outreach/ask``: 它把一个合成信封投给 Session,
去命中那条 ``fire=tool`` 的 TRIGGER, 让确定性工具在**零大模型**的前提下发出题库答案。
那条路径已整体移除 —— 答案现在一律由模型写, 而模型本来就在私聊那一轮里, 不需要 Gateway
再造一个事件把它叫起来。

``open_id`` **一律**取自 ``_feishu_webapp`` 的 cookie 身份, 绝不从 query/body 读 ——
否则任何人都能替别人作答。``qa_id`` 是第二道闸: 与 ``last_qa`` 不符即拒, 因此过期页面
无法重复作答 (与飞书那张一次性卡同一语义)。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from aiohttp import web
from loguru import logger

from psi_agent.gateway import _feishu_webapp

# 三个按钮的取值必须与 ``_outreach_confirm`` 里的常量一致 —— 页面和飞书卡片共用一套语义。
_ANSWERS = {"understood", "partial", "not_understood"}


def _load_workspace_module(workspace_root: str, name: str) -> Any:
    """从 agent 包的 ``tools/`` 载入一个模块 (与 supervisor/worker 的做法一致)。

    这些实现属于 agent 包而非 psi_agent 本体, 所以按路径载入而不是 import ——
    Gateway 不该把 workspace 的代码变成自己的依赖。
    """
    tools = Path(workspace_root) / "tools"
    target = tools / f"{name}.py"
    if not target.is_file():
        raise FileNotFoundError(f"workspace tool module not found: {target}")
    # 工具之间互相 import (``_outreach_confirm`` 等), 故 tools/ 必须在 sys.path 上。
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {target}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _state_file(oc: Any) -> Path:
    return oc.state_path()


def _scenario(oc: Any, state: dict[str, Any]) -> dict[str, Any]:
    return oc.scenario_config(state)


async def _resolve_identity(request: web.Request) -> str:
    """cookie → ``open_id``; 空串表示未登录。

    转调 ``_feishu_webapp`` 的共享实现 —— 这条判定 (只认 cookie, 不看 query/body) 在
    Gateway 里必须只有一份, 漂移一次就是越权。
    """
    return await _feishu_webapp.resolve_request_open_id(request)


def _workspace_root(request: web.Request) -> str:
    """agent 包根目录 —— 工具与 ``outreach/state.yaml`` 的落脚处。"""
    return str(request.app.get("outreach_workspace_root") or "")


async def handle_card(request: web.Request) -> web.Response:
    """页面渲染用: 该用户待确认的那张卡 (``last_qa``), 没有则 ``available: false``。"""
    open_id = await _resolve_identity(request)
    if not open_id:
        return web.json_response({"error": "未登录飞书网页应用"}, status=401)
    try:
        oc = _load_workspace_module(_workspace_root(request), "_outreach_confirm")
    except FileNotFoundError, ImportError:
        return web.json_response({"available": False, "reason": "scenario_3_not_enabled"})

    state_file = _state_file(oc)
    state = oc.read_yaml_mapping(state_file) or {}
    user = oc.find_user(state, open_id)
    last_qa = user.get("last_qa") if isinstance(user, dict) else None
    if not isinstance(last_qa, dict) or not last_qa.get("qa_id"):
        return web.json_response({"available": False})
    # 已答过的卡不再交给页面渲染 —— 与飞书那张一次性卡语义一致。
    if last_qa.get("answered_at"):
        return web.json_response({"available": False, "reason": "already_answered"})

    # 卡面只有一句提问加三个按钮, 所以这里不回查题库的摘要与检验题: 答案(含当期检验题)
    # 是机器人私聊里的上一条消息, 卡紧跟其后, 复述一遍只会让人读两遍。
    # ``prompt`` 直取 ``_outreach_confirm.CARD_PROMPT`` —— 与飞书那张卡共用一处措辞,
    # 不在这里另写一份默认值, 否则改了一处另一处照旧。
    return web.json_response(
        {
            "available": True,
            "qa_id": str(last_qa.get("qa_id") or ""),
            "prompt": oc.CARD_PROMPT,
            "keyword": str(last_qa.get("keyword") or ""),
            "topic": str(last_qa.get("topic") or ""),
        }
    )


async def handle_answer(request: web.Request) -> web.Response:
    """页面点了三个按钮之一 —— 走 ``outreach_confirm_handle`` 的同一批 helper 落库。"""
    open_id = await _resolve_identity(request)
    if not open_id:
        return web.json_response({"error": "未登录飞书网页应用"}, status=401)
    try:
        body = await request.json()
    except Exception as exc:
        return web.json_response({"error": f"请求体不是合法 JSON: {exc}"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "请求体必须是 JSON 对象"}, status=400)
    qa_id = str(body.get("qa_id") or "").strip()
    answer = str(body.get("answer") or "").strip()
    if not qa_id or answer not in _ANSWERS:
        return web.json_response({"error": f"需要 qa_id 与合法 answer ({'/'.join(sorted(_ANSWERS))})"}, status=400)

    try:
        oc = _load_workspace_module(_workspace_root(request), "_outreach_confirm")
    except FileNotFoundError, ImportError:
        return web.json_response({"error": "该 workspace 未启用场景 3"}, status=501)

    state_file = _state_file(oc)
    state = oc.read_yaml_mapping(state_file) or {}
    scenario = _scenario(oc, state)
    graduated_now = False
    question = ""

    def _mutate(row: dict[str, Any]) -> None:
        nonlocal graduated_now, question
        last_qa = row.get("last_qa")
        last_qa = last_qa if isinstance(last_qa, dict) else {}
        # qa_id 闸门: 与当前待确认的卡不符即什么都不做 (过期页面 / 重复提交)。
        if str(last_qa.get("qa_id") or "") != qa_id:
            raise LookupError("qa_id 与当前待确认的卡不符")
        if last_qa.get("answered_at"):
            raise LookupError("这张卡已经作答过了")
        question = str(last_qa.get("question") or "")
        topic = str(last_qa.get("topic") or "")
        # 与 outreach_confirm_handle 的 _mutate 逐字段一致 —— 两个入口写出的行必须同形,
        # 否则同一个用户在页面与机器人上答题会留下两种记录。
        oc.record_answer(row, answer, qa_id, question)
        last_qa["answered_at"] = oc.now_iso()
        last_qa["self_assessment"] = answer
        row["last_qa"] = last_qa
        if topic:
            row["node"] = topic
        graduated_now = oc.graduated(row, state)

    try:
        updated, err = oc.update_user(state_file, open_id, _mutate)
    except LookupError as exc:
        return web.json_response({"error": str(exc)}, status=409)
    except Exception as exc:
        logger.error(f"场景 3 作答落库失败: {exc!r}")
        return web.json_response({"error": f"作答失败: {exc}"}, status=500)
    if updated is None:
        return web.json_response({"error": err or "作答失败"}, status=400)

    logger.info(f"场景 3 (网页应用) 作答 answer={answer!r} graduated={graduated_now}")
    return web.json_response(
        {
            "ok": True,
            "answer": answer,
            "graduated": graduated_now,
            "closing": oc.closing_line(scenario, graduated_now),
        }
    )


def register(app: web.Application, *, workspace_root: str = "") -> None:
    """挂上网页应用读写理解确认卡的两个路由。``workspace_root`` 即 agent 包根目录。"""
    app["outreach_workspace_root"] = workspace_root
    app.router.add_get("/outreach/card", handle_card)
    app.router.add_post("/outreach/answer", handle_answer)
