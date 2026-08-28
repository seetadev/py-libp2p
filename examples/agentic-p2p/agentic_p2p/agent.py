"""Agent A / Agent B behavior.

Glues peer.py (networking), protocol.py (framing/routing), and
workflow.py (SeaLion-style orchestration) together. This module contains
no libp2p internals and no LLM internals — it just wires the pieces in the
order the design calls for:

    Agent A                         Agent B
       |                               |
       |---- /agent/task/1.0.0 ------->|
       |            TASK               |
       |                          Process task
       |                          Call LLM
       |                          Update sheet
       |<--------- RESULT -------------|
"""

from __future__ import annotations

import logging
from typing import Optional

from .config import Settings, get_settings
from .messages import ErrorMessage, ResultMessage, TaskMessage, new_task_id
from .peer import AgentPeer
from .protocol import read_message, write_message
from .workflow import Orchestrator, get_orchestrator

logger = logging.getLogger(__name__)


class Agent:
    """A single agent process. Can act as requester ("Agent A"), responder
    ("Agent B"), or both — the role is determined by which methods you call,
    not by a hardcoded flag.
    """

    def __init__(
        self,
        peer: AgentPeer,
        orchestrator: Optional[Orchestrator] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.peer = peer
        self.settings = settings or get_settings()
        self.orchestrator = orchestrator or get_orchestrator(self.settings)
        self._pending_results: dict[str, "trio.MemorySendChannel"] = {}

    # ---- Responder ("Agent B") side ----------------------------------

    async def on_inbound_stream(self, stream) -> None:
        """Registered as the libp2p stream handler. Reads one task, runs
        the workflow, writes back one result/error, then closes the stream.
        """
        try:
            message = await read_message(stream)
        except Exception as exc:  # noqa: BLE001 - malformed/hostile peer input
            logger.warning("Rejecting malformed inbound message: %s", exc)
            await write_message(
                stream, ErrorMessage(task_id="unknown", error=f"Malformed message: {exc}")
            )
            return

        if isinstance(message, TaskMessage):
            await self.handle_task(message, reply_stream=stream)
        else:
            logger.warning("Unexpected message type on inbound stream: %s", message.type)

    async def handle_task(self, message: TaskMessage, reply_stream=None) -> ResultMessage | ErrorMessage:
        """Task message -> Agent Router -> SeaLion workflow -> Result."""
        logger.info("Received task %s from %s", message.task_id, message.sender)
        try:
            result = await self.orchestrator.run(message.task)
        except Exception as exc:  # noqa: BLE001 - any workflow failure becomes an ErrorMessage
            logger.exception("Workflow failed for task %s", message.task_id)
            reply: ErrorMessage | ResultMessage = ErrorMessage(
                task_id=message.task_id, error=str(exc)
            )
        else:
            reply = ResultMessage(
                task_id=message.task_id,
                sender=self.peer.peer_id,
                status=result.status,
                summary=result.summary,
                sheet=result.sheet,
            )

        if reply_stream is not None:
            await write_message(reply_stream, reply)
        return reply

    async def handle_result(self, message: ResultMessage) -> None:
        logger.info("Received result for task %s: %s", message.task_id, message.summary)

    async def handle_error(self, message: ErrorMessage) -> None:
        logger.error("Received error for task %s: %s", message.task_id, message.error)

    # ---- Requester ("Agent A") side -----------------------------------

    async def send_task(self, peer_id: str, task_text: str) -> ResultMessage | ErrorMessage:
        """Create a Task, send it over libp2p, and wait for the Result."""
        task = TaskMessage(task_id=new_task_id(), sender=self.peer.peer_id, task=task_text)
        stream = await self.peer.open_task_stream(peer_id)
        try:
            await write_message(stream, task)
            reply = await read_message(stream)
        finally:
            try:
                await stream.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass

        if isinstance(reply, ErrorMessage):
            logger.error("Agent B returned an error for task %s: %s", task.task_id, reply.error)
        return reply
