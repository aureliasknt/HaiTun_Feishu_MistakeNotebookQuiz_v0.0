"""Feishu interactive-card callback parsing, consumption, and dispatch."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anyio
from lark_channel.core.enum import AccessTokenType, HttpMethod
from lark_channel.core.model import BaseRequest
from loguru import logger

from ._card_store import CardSnapshot, pop_card_snapshot

_INTERACTIVE_CARD_TAGS = {"action", "form"}
_REMOVED_CARD_ELEMENT = object()

type MarkSeen = Callable[[str], bool]

_SAVE_PENDING = "⏳ 正在保存你的答案…"
_SAVE_SUCCESS = "✅ 已记录"
_SAVE_FAILURE = "⚠️ 保存失败。答题反馈不受影响。请联系管理员补录。"
_BITABLE_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class _QuizAction:
    matched: bool
    question_text: str
    theme: str
    correct_answer: str
    question_id: str
    app_token: str
    table_id: str
    employee_open_id: str
    recipient_name: str
    selected_answer: str
    verdict: str


def _normalize_card_action_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _find_card_action_label(value: Any, action_value: Any) -> str | None:
    normalized_action_value = _normalize_card_action_value(action_value)
    if isinstance(value, dict):
        if "value" in value and _normalize_card_action_value(value["value"]) == normalized_action_value:
            text = value.get("text")
            if isinstance(text, str):
                label = text or None
            elif isinstance(text, dict):
                content = text.get("content")
                label = content if isinstance(content, str) and content else None
            else:
                label = None
            if label:
                return label
        for child in value.values():
            label = _find_card_action_label(child, action_value)
            if label:
                return label
    elif isinstance(value, list):
        for child in value:
            label = _find_card_action_label(child, action_value)
            if label:
                return label
    return None


def _remove_card_interactions(
    value: Any,
    action_value: Any,
    selected_label: str,
    selected_replaced: bool = False,
) -> tuple[Any, bool]:
    if isinstance(value, dict):
        if value.get("tag") in _INTERACTIVE_CARD_TAGS:
            if not selected_replaced and _find_card_action_label(value, action_value):
                return (
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"已选择: {selected_label}",
                            }
                        ],
                    },
                    True,
                )
            return _REMOVED_CARD_ELEMENT, selected_replaced

        result: dict[str, Any] = {}
        for key, child in value.items():
            cleaned, selected_replaced = _remove_card_interactions(
                child,
                action_value,
                selected_label,
                selected_replaced,
            )
            if cleaned is not _REMOVED_CARD_ELEMENT:
                result[key] = cleaned
        return result, selected_replaced

    if isinstance(value, list):
        result: list[Any] = []
        for child in value:
            cleaned, selected_replaced = _remove_card_interactions(
                child,
                action_value,
                selected_label,
                selected_replaced,
            )
            if cleaned is not _REMOVED_CARD_ELEMENT:
                result.append(cleaned)
        return result, selected_replaced

    return value, selected_replaced


def _consumed_card_content(card: Any, action_value: Any) -> dict[str, Any] | None:
    if action_value is None or not isinstance(card, dict):
        return None
    selected_label = _find_card_action_label(card, action_value)
    if not selected_label:
        return None
    consumed, selected_replaced = _remove_card_interactions(card, action_value, selected_label)
    return consumed if selected_replaced and isinstance(consumed, dict) else None


def _quiz_action(
    event: Any,
    *,
    snapshot: CardSnapshot | None = None,
    snapshot_status: str = "not_found",
) -> _QuizAction:
    operator = getattr(event, "operator", None)
    operator_open_id = getattr(operator, "open_id", None)
    action = getattr(event, "action", None)
    raw = getattr(event, "raw", None)
    raw_event = raw.get("event") if isinstance(raw, dict) else None
    raw_action = raw_event.get("action") if isinstance(raw_event, dict) else None
    if not isinstance(raw_action, dict):
        raw_action = {}

    value = getattr(action, "value", None)
    if value is None:
        value = raw_action.get("value")

    normalized_value = _normalize_card_action_value(value)
    action_id = None
    if isinstance(normalized_value, dict):
        for key in ("action", "action_id"):
            raw_action_id = normalized_value.get(key)
            if isinstance(raw_action_id, str) and raw_action_id and raw_action_id.strip() == raw_action_id:
                action_id = raw_action_id
                break

    action_handlers = snapshot.action_handlers if snapshot is not None else None
    if snapshot is None or snapshot_status == "invalid":
        matched = False
    elif action_handlers:
        matched = action_id in action_handlers
    else:
        matched = action_id is not None

    question_text = ""
    theme = ""
    correct_answer = ""
    question_id = ""
    app_token = ""
    table_id = ""
    employee_open_id = ""
    recipient_name = ""
    if snapshot is not None:
        business_context = snapshot.business_context
        if isinstance(business_context, dict):
            question_text = str(business_context.get("question_text") or "")
            theme = str(business_context.get("theme") or "")
            correct_answer = str(business_context.get("correct_answer") or "")
            question_id = str(business_context.get("question_id") or "")
            app_token = str(business_context.get("app_token") or "")
            table_id = str(business_context.get("table_id") or "")
            employee_open_id = str(business_context.get("employee_open_id") or "")
            recipient_name = str(business_context.get("recipient_name") or "")

    if not employee_open_id:
        employee_open_id = str(operator_open_id or "")

    selected_answer = ""
    if isinstance(action_id, str) and len(action_id) >= 8 and action_id.startswith("answer_"):
        selected_answer = action_id.rsplit("_", 1)[-1].upper()
    verdict = ""
    if selected_answer and correct_answer:
        verdict = "对" if selected_answer.upper() == correct_answer.upper() else "错"

    return _QuizAction(
        matched=matched,
        question_text=question_text,
        theme=theme,
        correct_answer=correct_answer,
        question_id=question_id,
        app_token=app_token,
        table_id=table_id,
        employee_open_id=employee_open_id,
        recipient_name=recipient_name,
        selected_answer=selected_answer,
        verdict=verdict,
    )


def _card_action_feedback(action: _QuizAction) -> str:
    """Grade a quiz click deterministically without invoking an LLM."""
    if not action.matched:
        return "⚠️ 无法识别这次答题。请联系管理员重新发送题目。"
    if not action.selected_answer or not action.correct_answer or not action.verdict:
        return "⚠️ 这次答题缺少必要信息。暂时无法判定结果。"
    if action.verdict == "对":
        return "✅ 回答正确。"
    return f"❌ 回答错误。你选择了 {action.selected_answer}。正确答案是 {action.correct_answer}。"


def _card_action_record(action: _QuizAction) -> dict[str, Any] | None:
    """Build the exact Base row; return None when writing would be unsafe."""
    normalized_question = action.question_id.strip() or action.question_text.strip()
    if (
        not action.matched
        or not action.app_token
        or not action.table_id
        or not action.employee_open_id
        or not action.recipient_name
        or not normalized_question
        or not action.selected_answer
        or not action.correct_answer
        or not action.verdict
    ):
        return None
    return {
        "员工": action.employee_open_id,
        "收件人姓名": action.recipient_name,
        "题目": normalized_question,
        "主题": action.theme,
        "选择": action.selected_answer.upper(),
        "正确答案": action.correct_answer.upper(),
        "判定": action.verdict,
        "日期": time.time_ns() // 1_000_000,
    }


def _create_record_request(action: _QuizAction, fields: dict[str, Any]) -> BaseRequest:
    request = BaseRequest()
    request.http_method = HttpMethod.POST
    request.uri = "/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records"
    request.paths["app_token"] = action.app_token
    request.paths["table_id"] = action.table_id
    request.token_types = {AccessTokenType.TENANT}
    request.body = {"fields": fields}
    return request


def _get_record_request(action: _QuizAction, record_id: str) -> BaseRequest:
    request = BaseRequest()
    request.http_method = HttpMethod.GET
    request.uri = "/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/:record_id"
    request.paths["app_token"] = action.app_token
    request.paths["table_id"] = action.table_id
    request.paths["record_id"] = record_id
    request.token_types = {AccessTokenType.TENANT}
    return request


def _bitable_response_data(response: Any) -> dict[str, Any]:
    raw = getattr(response, "raw", None)
    content = getattr(raw, "content", None) if raw is not None else None
    if not content:
        raise RuntimeError(f"empty Feishu Base response (code={getattr(response, 'code', None)!r})")
    try:
        body = json.loads(bytes(content).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise RuntimeError("invalid Feishu Base response") from e
    if not isinstance(body, dict):
        raise RuntimeError("invalid Feishu Base response shape")
    code = body.get("code", getattr(response, "code", None))
    if code != 0:
        raise RuntimeError(f"Feishu Base rejected the request (code={code!r}, msg={body.get('msg', '')!r})")
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Feishu Base response is missing data")
    return data


async def _save_quiz_answer(channel: Any, action: _QuizAction, fields: dict[str, Any]) -> str:
    """Create one row and verify it by id, with no LLM and no write retry."""
    with anyio.fail_after(_BITABLE_TIMEOUT_SECONDS):
        create_response = await channel.client.arequest(_create_record_request(action, fields))
        create_data = _bitable_response_data(create_response)
        created = create_data.get("record")
        if (
            not isinstance(created, dict)
            or not isinstance(created.get("record_id"), str)
            or not created["record_id"]
        ):
            raise RuntimeError("Feishu Base create response is missing record_id")
        record_id = created["record_id"]
        get_response = await channel.client.arequest(_get_record_request(action, record_id))
        get_data = _bitable_response_data(get_response)
        saved = get_data.get("record")
        if not isinstance(saved, dict) or saved.get("record_id") != record_id:
            raise RuntimeError("Feishu Base readback did not return the created record")
        saved_fields = saved.get("fields")
        if not isinstance(saved_fields, dict):
            raise RuntimeError("Feishu Base readback is missing fields")
        missing_fields = [name for name in fields if name not in saved_fields]
        if missing_fields:
            raise RuntimeError(f"Feishu Base readback is missing fields: {missing_fields!r}")
    return record_id


async def _finish_save_status(channel: Any, chat_id: str, status_result: Any, text: str) -> None:
    message_id = getattr(status_result, "message_id", None)
    if message_id:
        try:
            edit_result = await channel.edit_message(message_id, {"text": text})
            if getattr(edit_result, "success", False):
                return
            logger.warning(f"failed to edit answer-save status {message_id} — {getattr(edit_result, 'error', None)!r}")
        except Exception as e:
            logger.warning(f"failed to edit answer-save status {message_id} — {e!r}")
    try:
        result = await channel.send(chat_id, {"text": text})
        if not getattr(result, "success", False):
            logger.warning(f"failed to send final answer-save status — {getattr(result, 'error', None)!r}")
    except Exception as e:
        logger.error(f"failed to send final answer-save status — {e!r}")


async def handle_card_action(
    channel: Any,
    allowed_ids: list[str] | None,
    mark_seen: MarkSeen,
    event: Any,
    appdata: str = "",
) -> None:
    """Route a Feishu card action into the operator's agent session."""
    chat_id = ""
    try:
        operator = getattr(event, "operator", None)
        operator_open_id = getattr(operator, "open_id", None)
        chat_id = getattr(event, "chat_id", "") or ""
        message_id = getattr(event, "message_id", "") or ""

        if not operator_open_id:
            logger.warning("card action missing operator.open_id, skipping")
            return
        if not chat_id:
            logger.warning("card action missing chat_id, skipping")
            return
        if not message_id:
            logger.warning("card action missing message_id, cannot enforce single-use card")
            return
        if allowed_ids is not None and operator_open_id not in allowed_ids:
            logger.debug(f"card action operator {operator_open_id} blocked by whitelist")
            return
        if not mark_seen(message_id):
            logger.info(f"card action ignored for already-consumed message={message_id}")
            return

        action = getattr(event, "action", None)
        action_value = getattr(action, "value", None)
        if action_value is None:
            raw = getattr(event, "raw", None)
            raw_event = raw.get("event") if isinstance(raw, dict) else None
            raw_action = raw_event.get("action") if isinstance(raw_event, dict) else None
            action_value = raw_action.get("value") if isinstance(raw_action, dict) else None

        snapshot = None
        snapshot_status = "error"
        replacement = None
        try:
            claim = await pop_card_snapshot(message_id, appdata)
            if claim.status == "already_consumed":
                logger.info(f"card action ignored for durably-consumed message={message_id}")
                return
            snapshot_status = claim.status
            snapshot = claim.snapshot
            if snapshot is not None:
                replacement = _consumed_card_content(snapshot.card, action_value)
                if replacement is None:
                    logger.warning(f"failed to consume card snapshot {message_id}, trying Feishu payload")
        except Exception as e:
            logger.warning(f"failed to load card snapshot {message_id}, trying Feishu payload — {e!r}")

        if replacement is None:
            try:
                payload = await channel.fetch_message(message_id)
                fetched_card = None
                if isinstance(payload, dict):
                    data = payload.get("data")
                    items = data.get("items") if isinstance(data, dict) else None
                    if isinstance(items, list):
                        for item in items:
                            if not isinstance(item, dict) or item.get("msg_type") != "interactive":
                                continue
                            body = item.get("body")
                            content = body.get("content") if isinstance(body, dict) else None
                            if isinstance(content, dict):
                                fetched_card = content
                                break
                            if not isinstance(content, str):
                                continue
                            try:
                                parsed_card = json.loads(content)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(parsed_card, dict):
                                fetched_card = parsed_card
                                break
                replacement = _consumed_card_content(fetched_card, action_value)
                if replacement is None:
                    logger.warning(f"failed to preserve consumed card {message_id}, using fallback")
            except Exception as e:
                logger.warning(f"failed to fetch consumed card {message_id}, using fallback — {e!r}")

        if replacement is None:
            replacement = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "green",
                    "title": {"tag": "plain_text", "content": "已提交"},
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": "你的操作已提交, 请查看本会话中的处理结果。",
                    }
                ],
            }
        try:
            result = await channel.update_card(message_id, replacement)
            if not getattr(result, "success", False):
                logger.warning(f"failed to mark card {message_id} consumed — {getattr(result, 'error', None)!r}")
        except Exception as e:
            logger.warning(f"failed to mark card {message_id} consumed — {e!r}")

        action_context = _quiz_action(event, snapshot=snapshot, snapshot_status=snapshot_status)
        feedback_result = await channel.send(chat_id, {"text": _card_action_feedback(action_context)})
        if not getattr(feedback_result, "success", False):
            logger.warning(f"failed to send hardcoded grading feedback — {getattr(feedback_result, 'error', None)!r}")
        logger.debug("hardcoded card-action grading feedback sent")

        if not action_context.matched:
            return
        record = _card_action_record(action_context)
        if record is None:
            logger.warning(f"answer not saved: missing or unsafe write context for message={message_id}")
            await _finish_save_status(channel, chat_id, None, _SAVE_FAILURE)
            return

        status_result = None
        try:
            status_result = await channel.send(chat_id, {"text": _SAVE_PENDING})
            if not getattr(status_result, "success", False):
                logger.warning(f"failed to show answer-save progress — {getattr(status_result, 'error', None)!r}")
        except Exception as e:
            logger.warning(f"failed to show answer-save progress — {e!r}")

        save_succeeded = False
        try:
            record_id = await _save_quiz_answer(channel, action_context, record)
            save_succeeded = True
            logger.info(f"quiz answer saved directly message={message_id} record_id={record_id}")
        except Exception as e:
            logger.error(f"direct answer-save failed message={message_id} — {e!r}")

        final_status = _SAVE_SUCCESS if save_succeeded else _SAVE_FAILURE
        await _finish_save_status(channel, chat_id, status_result, final_status)
        logger.debug(f"card action save completed success={save_succeeded}")
    except Exception as e:
        logger.error(f"Card action handling error — {e!r}")
        if not chat_id:
            return
        try:
            await channel.send(chat_id, {"text": f"Error: {e}"})
        except Exception as notify_error:
            logger.error(f"Card action error notification failed — {notify_error!r}")
