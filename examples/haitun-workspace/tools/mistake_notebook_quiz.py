"""Deterministic, stateful sender for the Feishu mistake-notebook quiz."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import _runtime_paths as _paths
import anyio
from feishu_message import feishu_message_send_card


@dataclass(frozen=True)
class _Question:
    question_id: str
    theme: str
    text: str
    options: tuple[str, str, str, str]
    correct_answer: str


@dataclass(frozen=True)
class _QuizState:
    next_index: int = 0
    last_sent_at: datetime | None = None


_QUESTIONS = (
    _Question(
        "q1",
        "外部成果",
        "一个大目标要满足什么条件才算数?",
        ("团队内部认为完成了就算", "成果必须来自外部", "项目经理确认了就算", "有清晰的时间节点就算"),
        "B",
    ),
    _Question(
        "q2",
        "价值观",
        "为了让自己看起来更努力, 把TODO list写得比实际进度快, 这属于什么?",
        ("可以接受的小技巧", "红线行为, 不允许", "只要后面补上就没关系", "没被发现就不算问题"),
        "B",
    ),
    _Question(
        "q3",
        "执行力",
        "TODO最核心要看哪两点?",
        (
            "是否写得详细, 是否有截止日期",
            "按时按质按量, 有没有给用户带来价值",
            "完成速度, 团队人数",
            "领导是否满意, 字数多少",
        ),
        "B",
    ),
    _Question(
        "q4",
        "来自评论区的真实分歧",
        "员工应该先写TODO再让mentor检查, 还是mentor先检查再写?",
        ("先写, mentor之后检查", "mentor先检查, 员工再写", "每周统一开会检查一次", "不需要mentor检查"),
        "A",
    ),
)
_ACTION_HANDLERS = {
    "answer_a": "mistake_notebook_grade_answer",
    "answer_b": "mistake_notebook_grade_answer",
    "answer_c": "mistake_notebook_grade_answer",
    "answer_d": "mistake_notebook_grade_answer",
}
_RECIPIENT_SAFE = re.compile(r"[^A-Za-z0-9._-]")
_lock = anyio.Lock()


def _schedule_tz() -> ZoneInfo | None:
    name = os.environ.get("TZ", "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _now_local() -> datetime:
    tz = _schedule_tz()
    return datetime.now(tz).replace(tzinfo=None) if tz is not None else datetime.now()


def _parse_local(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    tz = _schedule_tz()
    localized = parsed.astimezone(tz) if tz is not None else parsed.astimezone()
    return localized.replace(tzinfo=None)


def _state_path(receive_id: str) -> anyio.Path:
    safe_id = _RECIPIENT_SAFE.sub("_", receive_id)
    return _paths.resolve_workspace() / ".psi" / "mistake-notebook-quiz" / f"{safe_id}.json"


async def _load_state(path: anyio.Path) -> _QuizState:
    if not await path.exists():
        return _QuizState()
    try:
        data = json.loads(await path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _QuizState()
    if not isinstance(data, dict):
        return _QuizState()
    value = data.get("next_index")
    index = value % len(_QUESTIONS) if isinstance(value, int) and value >= 0 else 0
    raw_last_sent = data.get("last_sent_at") or data.get("updated_at")
    try:
        last_sent_at = _parse_local(raw_last_sent) if isinstance(raw_last_sent, str) else None
    except ValueError:
        last_sent_at = None
    return _QuizState(next_index=index, last_sent_at=last_sent_at)


async def _save_state(path: anyio.Path, state: _QuizState) -> None:
    await path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f"{path.name}.tmp"
    payload = json.dumps(
        {
            "next_index": state.next_index,
            "last_sent_at": state.last_sent_at.isoformat() if state.last_sent_at is not None else None,
            "updated_at": _now_local().isoformat(),
        },
        ensure_ascii=False,
    )
    await temp.write_text(payload, encoding="utf-8")
    await temp.replace(path)


def _parse_clock(value: str) -> time:
    return datetime.strptime(value.strip(), "%H:%M").time()


def _build_card(question: _Question) -> dict[str, Any]:
    actions = []
    for letter, option in zip("ABCD", question.options, strict=True):
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": f"{letter} {option}"},
                "value": {"action": f"answer_{letter.casefold()}"},
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"错题本测验 · {question.theme}"},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": f"问题: {question.text}"},
            {"tag": "action", "actions": actions},
        ],
    }


def _error(message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": "quiz_send_failed", "message": message, "retryable": True}},
        ensure_ascii=False,
    )


async def mistake_notebook_quiz_send_next(
    receive_id: str,
    app_token: str,
    table_id: str,
    recipient_name: str = "",
    interval_minutes: int = 60,
    window_start: str = "08:00",
    window_end: str = "22:00",
    not_before: str = "",
    reset: bool = False,
) -> str:
    """Send the recipient's next quiz card and advance only after confirmed delivery.

    Args:
        receive_id: Recipient Feishu open_id (``ou_...``).
        app_token: Feishu Base app token used when grading the click.
        table_id: Resolved answer-record table id.
        recipient_name: Recipient display name to persist with the answer record.
        interval_minutes: Minimum minutes between cards for this recipient.
        window_start: Earliest local send time in HH:MM form.
        window_end: Latest local send time in HH:MM form.
        not_before: Optional local/ISO datetime. Earlier recurring fires are skipped.
        reset: Start this recipient again from q1 before sending.
    """
    recipient = receive_id.strip()
    if not recipient.startswith("ou_"):
        return _error("receive_id must be a real Feishu open_id beginning with 'ou_'")
    if not app_token.strip() or not table_id.strip():
        return _error("app_token and table_id are required")
    if (
        not isinstance(interval_minutes, int)
        or isinstance(interval_minutes, bool)
        or not 1 <= interval_minutes <= 1440
    ):
        return _error("interval_minutes must be an integer from 1 through 1440")
    try:
        start_clock = _parse_clock(window_start)
        end_clock = _parse_clock(window_end)
    except ValueError:
        return _error("window_start and window_end must use HH:MM")
    if start_clock > end_clock:
        return _error("window_start must not be later than window_end")
    now = _now_local()
    if not start_clock <= now.time() <= end_clock:
        return json.dumps(
            {"ok": True, "skipped": True, "reason": "outside_window"},
            ensure_ascii=False,
        )
    if not_before.strip():
        try:
            threshold = _parse_local(not_before)
        except ValueError:
            return _error("not_before must be an ISO-8601 or YYYY-MM-DD HH:MM datetime")
        if now < threshold:
            return json.dumps(
                {"ok": True, "skipped": True, "reason": "not_before", "not_before": not_before},
                ensure_ascii=False,
            )

    async with _lock:
        path = _state_path(recipient)
        state = await _load_state(path)
        if not reset and state.last_sent_at is not None:
            next_allowed = state.last_sent_at + timedelta(minutes=interval_minutes)
            if now < next_allowed:
                return json.dumps(
                    {
                        "ok": True,
                        "skipped": True,
                        "reason": "interval",
                        "next_allowed": next_allowed.isoformat(timespec="minutes"),
                    },
                    ensure_ascii=False,
                )
        index = 0 if reset else state.next_index
        question = _QUESTIONS[index]
        business_context = {
            "question_id": question.question_id,
            "theme": question.theme,
            "question_text": question.text,
            "correct_answer": question.correct_answer,
            "employee_open_id": recipient,
            "recipient_name": recipient_name.strip(),
            "app_token": app_token.strip(),
            "table_id": table_id.strip(),
        }
        raw = await feishu_message_send_card(
            receive_id=recipient,
            receive_id_type="open_id",
            card_json=json.dumps(_build_card(question), ensure_ascii=False, separators=(",", ":")),
            business_context_json=json.dumps(business_context, ensure_ascii=False, separators=(",", ":")),
            action_handlers_json=json.dumps(_ACTION_HANDLERS, ensure_ascii=False, separators=(",", ":")),
        )
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("quiz card send returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError(f"quiz card send failed: {raw}")
        if result.get("callback_context_saved") is not True:
            raise RuntimeError("quiz card was sent but its callback context was not saved")

        sent_at = now.replace(second=0, microsecond=0)
        await _save_state(
            path,
            _QuizState(next_index=(index + 1) % len(_QUESTIONS), last_sent_at=sent_at),
        )
        return json.dumps(
            {
                "ok": True,
                "sent": True,
                "question_id": question.question_id,
                "receive_id": recipient,
                "message_id": result.get("message_id", ""),
            },
            ensure_ascii=False,
        )
