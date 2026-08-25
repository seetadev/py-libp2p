import time
import uuid
from dataclasses import dataclass

import trio


@dataclass
class Operation:
    operation_id: str
    agent_id: str
    agent_name: str
    role: str
    content: str
    timestamp: float

    def to_dict(self):
        return {
            "operation_id": self.operation_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, value):
        return cls(
            operation_id=str(value["operation_id"]),
            agent_id=str(value["agent_id"]),
            agent_name=str(value["agent_name"]),
            role=str(value["role"]),
            content=str(value["content"]),
            timestamp=float(value["timestamp"]),
        )


class SharedState:
    def __init__(self):
        self.operations = {}
        self.lock = trio.Lock()

    async def add(self, agent_id, agent_name, role, content):
        operation = Operation(
            operation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            agent_name=agent_name,
            role=role,
            content=content,
            timestamp=time.time(),
        )

        data = operation.to_dict()

        async with self.lock:
            self.operations[operation.operation_id] = data

        return data

    async def merge(self, operation):
        op = Operation.from_dict(operation)

        async with self.lock:
            if op.operation_id in self.operations:
                return False

            self.operations[op.operation_id] = op.to_dict()
            return True

    async def snapshot(self):
        async with self.lock:
            operations = list(self.operations.values())

        return sorted(operations, key=lambda x: x["timestamp"])

    async def recent(self, count=12):
        return (await self.snapshot())[-count:]
