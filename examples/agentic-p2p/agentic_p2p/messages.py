"""Wire message schemas for the /agent/task/1.0.0 protocol.

These are the ONLY shapes of data that ever cross the libp2p stream.
Everything received from the network is parsed through these Pydantic
models before it touches any agent logic — untrusted bytes never reach
`eval`, `exec`, or anything resembling them.
"""

from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

PROTOCOL_ID = "/agent/task/1.0.0"


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


class TaskMessage(BaseModel):
    type: Literal["task"] = "task"
    task_id: str = Field(default_factory=new_task_id)
    sender: str
    task: str
    timestamp: float = Field(default_factory=time.time)

    @field_validator("task")
    @classmethod
    def task_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be a non-empty string")
        if len(v) > 20_000:
            raise ValueError("task exceeds maximum allowed length (20000 chars)")
        return v

    @field_validator("sender")
    @classmethod
    def sender_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("sender must be a non-empty peer id")
        return v


class ResultMessage(BaseModel):
    type: Literal["result"] = "result"
    task_id: str
    sender: str
    status: Literal["completed", "completed_with_warnings"] = "completed"
    summary: str
    sheet: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    task_id: str
    error: str
    timestamp: float = Field(default_factory=time.time)


# Union type used when decoding an incoming payload of unknown kind.
AnyMessage = TaskMessage | ResultMessage | ErrorMessage


class MessageDecodeError(ValueError):
    """Raised when raw bytes/dict cannot be turned into a known message type."""


def parse_message(payload: dict) -> AnyMessage:
    """Validate an arbitrary dict against the known message schemas.

    This is the single choke point untrusted network data passes through.
    """
    msg_type = payload.get("type")
    if msg_type == "task":
        return TaskMessage.model_validate(payload)
    if msg_type == "result":
        return ResultMessage.model_validate(payload)
    if msg_type == "error":
        return ErrorMessage.model_validate(payload)
    raise MessageDecodeError(f"Unknown or missing message type: {msg_type!r}")
