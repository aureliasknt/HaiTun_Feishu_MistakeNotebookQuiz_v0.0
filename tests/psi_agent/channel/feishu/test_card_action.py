from __future__ import annotations

from types import SimpleNamespace

from psi_agent.channel.feishu._card_action import (
    _bitable_response_data,
    _card_action_feedback,
    _card_action_record,
    _create_record_request,
    _get_record_request,
    _quiz_action,
)
from psi_agent.channel.feishu._card_store import CardSnapshot


def _event(*, open_id: str = "ou_clicker", action: str = "answer_b") -> SimpleNamespace:
    return SimpleNamespace(
        operator=SimpleNamespace(open_id=open_id),
        action=SimpleNamespace(tag="button", value={"action": action}),
        raw={"event": {"action": {"tag": "button", "value": {"action": action}}}},
    )


def test_card_action_feedback_grades_correct_answer_without_llm() -> None:
    snapshot = CardSnapshot(
        card={},
        business_context={
            "question_id": "q1",
            "theme": "外部成果",
            "question_text": "一个大目标要满足什么条件才算数?",
            "correct_answer": "B",
            "employee_open_id": "ou_target",
            "recipient_name": "测试收件人",
            "app_token": "bascn_xxx",
            "table_id": "tbl_xxx",
        },
        action_handlers={"answer_b": "mistake_notebook_grade_answer"},
    )

    action = _quiz_action(_event(action="answer_b"), snapshot=snapshot, snapshot_status="claimed")

    assert _card_action_feedback(action) == "✅ 回答正确。"


def test_card_action_record_contains_normalized_fields() -> None:
    snapshot = CardSnapshot(
        card={},
        business_context={
            "question_id": "q1",
            "theme": "外部成果",
            "question_text": "一个大目标要满足什么条件才算数?",
            "correct_answer": "B",
            "employee_open_id": "ou_target",
            "recipient_name": "测试收件人",
            "app_token": "bascn_xxx",
            "table_id": "tbl_xxx",
        },
        action_handlers={"answer_b": "mistake_notebook_grade_answer"},
    )

    action = _quiz_action(_event(action="answer_b"), snapshot=snapshot, snapshot_status="claimed")
    record = _card_action_record(action)

    assert record is not None
    assert record["员工"] == "ou_target"
    assert record["收件人姓名"] == "测试收件人"
    assert record["题目"] == "q1"
    assert record["主题"] == "外部成果"
    assert record["选择"] == "B"
    assert record["正确答案"] == "B"
    assert record["判定"] == "对"
    assert isinstance(record["日期"], int)

    create_request = _create_record_request(action, record)
    assert create_request.paths == {"app_token": "bascn_xxx", "table_id": "tbl_xxx"}
    assert create_request.body == {"fields": record}
    assert len(create_request.token_types) == 1

    get_request = _get_record_request(action, "rec_xxx")
    assert get_request.paths["record_id"] == "rec_xxx"


def test_card_action_record_refuses_missing_coordinates() -> None:
    snapshot = CardSnapshot(
        card={},
        business_context={
            "question_id": "q2",
            "theme": "价值观",
            "question_text": "为了让自己看起来更努力, 把TODO list写得比实际进度快, 这属于什么?",
            "correct_answer": "B",
        },
        action_handlers={"answer_a": "mistake_notebook_grade_answer"},
    )

    action = _quiz_action(_event(action="answer_a"), snapshot=snapshot, snapshot_status="claimed")

    assert _card_action_record(action) is None


def test_bitable_response_data_parses_generic_sdk_response() -> None:
    payload = b'{"code":0,"data":{"record":{"record_id":"rec_xxx"}}}'
    response = SimpleNamespace(code=0, raw=SimpleNamespace(content=payload))

    assert _bitable_response_data(response)["record"]["record_id"] == "rec_xxx"


def test_card_action_feedback_rejects_unmatched_click() -> None:
    snapshot = CardSnapshot(
        card={},
        business_context={"question_id": "q3", "correct_answer": "A"},
        action_handlers={"answer_a": "mistake_notebook_grade_answer"},
    )

    action = _quiz_action(_event(action="answer_d"), snapshot=snapshot, snapshot_status="claimed")

    assert _card_action_feedback(action).startswith("⚠️ 无法识别这次答题。")


def test_card_action_feedback_shows_selected_and_correct_answer() -> None:
    snapshot = CardSnapshot(
        card={},
        business_context={"question_id": "q3", "correct_answer": "A"},
        action_handlers={"answer_d": "mistake_notebook_grade_answer"},
    )

    action = _quiz_action(_event(action="answer_d"), snapshot=snapshot, snapshot_status="claimed")

    assert _card_action_feedback(action) == "❌ 回答错误。你选择了 D。正确答案是 A。"
