import pytest

from agentic_p2p.messages import ErrorMessage, MessageDecodeError, ResultMessage, TaskMessage
from agentic_p2p.protocol import Router, encode_message, read_message, write_message


class FakeStream:
    """A minimal in-memory stand-in for an INetStream, one direction of bytes."""

    def __init__(self, initial: bytes = b"") -> None:
        self._buf = bytearray(initial)
        self._written = bytearray()

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = len(self._buf)
        chunk = bytes(self._buf[:n])
        del self._buf[:n]
        return chunk

    async def write(self, data: bytes) -> None:
        self._written.extend(data)

    @property
    def written(self) -> bytes:
        return bytes(self._written)

    def feed(self, data: bytes) -> None:
        self._buf.extend(data)


async def test_encode_and_read_message_roundtrip():
    task = TaskMessage(sender="peer-a", task="Analyze the sales data")
    frame = encode_message(task)

    stream = FakeStream(frame)
    decoded = await read_message(stream)

    assert isinstance(decoded, TaskMessage)
    assert decoded.task == "Analyze the sales data"
    assert decoded.task_id == task.task_id


async def test_write_message_then_read_message():
    stream = FakeStream()
    result = ResultMessage(task_id="t1", sender="peer-b", summary="done")
    await write_message(stream, result)

    # Feed our own output back in to simulate the other side reading it.
    reader = FakeStream(stream.written)
    decoded = await read_message(reader)
    assert isinstance(decoded, ResultMessage)
    assert decoded.summary == "done"


async def test_read_message_rejects_bad_json():
    bad_payload = b"not json"
    frame = len(bad_payload).to_bytes(4, "big") + bad_payload
    stream = FakeStream(frame)
    with pytest.raises(MessageDecodeError):
        await read_message(stream)


async def test_read_message_raises_on_premature_close():
    # Declare 100 bytes but supply none.
    frame = (100).to_bytes(4, "big")
    stream = FakeStream(frame)
    with pytest.raises(ConnectionError):
        await read_message(stream)


async def test_read_message_rejects_oversized_declared_length():
    huge_len = (10 * 1024 * 1024).to_bytes(4, "big")
    stream = FakeStream(huge_len)
    with pytest.raises(ValueError):
        await read_message(stream)


async def test_router_dispatches_to_correct_handler():
    calls = []

    class DummyAgent:
        async def handle_task(self, msg):
            calls.append(("task", msg.task_id))

        async def handle_result(self, msg):
            calls.append(("result", msg.task_id))

        async def handle_error(self, msg):
            calls.append(("error", msg.task_id))

    router = Router(DummyAgent())
    await router.dispatch(TaskMessage(task_id="t1", sender="a", task="do x"))
    await router.dispatch(ResultMessage(task_id="t2", sender="b", summary="ok"))
    await router.dispatch(ErrorMessage(task_id="t3", error="boom"))

    assert calls == [("task", "t1"), ("result", "t2"), ("error", "t3")]
