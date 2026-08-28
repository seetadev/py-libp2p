import pytest
from pydantic import ValidationError

from agentic_p2p.messages import (
    ErrorMessage,
    MessageDecodeError,
    ResultMessage,
    TaskMessage,
    parse_message,
)


def test_task_message_defaults():
    msg = TaskMessage(sender="peer-a", task="Analyze the sales data")
    assert msg.type == "task"
    assert msg.task_id  # auto-generated
    assert msg.timestamp > 0


def test_task_message_rejects_empty_task():
    with pytest.raises(ValidationError):
        TaskMessage(sender="peer-a", task="   ")


def test_task_message_rejects_empty_sender():
    with pytest.raises(ValidationError):
        TaskMessage(sender="", task="Analyze the sales data")


def test_task_message_rejects_oversized_task():
    with pytest.raises(ValidationError):
        TaskMessage(sender="peer-a", task="x" * 20_001)


def test_result_message_roundtrip():
    msg = ResultMessage(
        task_id="abc123", sender="peer-b", summary="Top product: A", sheet="sales-analysis"
    )
    payload = msg.model_dump()
    assert payload["type"] == "result"
    rebuilt = parse_message(payload)
    assert isinstance(rebuilt, ResultMessage)
    assert rebuilt.summary == "Top product: A"


def test_error_message_roundtrip():
    msg = ErrorMessage(task_id="abc123", error="LLM request failed")
    rebuilt = parse_message(msg.model_dump())
    assert isinstance(rebuilt, ErrorMessage)
    assert rebuilt.error == "LLM request failed"


def test_parse_message_rejects_unknown_type():
    with pytest.raises(MessageDecodeError):
        parse_message({"type": "not_a_real_type"})


def test_parse_message_rejects_missing_type():
    with pytest.raises(MessageDecodeError):
        parse_message({"task_id": "abc123"})
