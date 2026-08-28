"""Integration test: two real in-process libp2p peers exchange a task and a
result over a real stream on /agent/task/1.0.0. Only the LLM and EtherCalc
are mocked — the network path is genuine.

Skipped automatically if py-libp2p isn't installed in the current
environment (`pip install -r requirements.txt` to enable it).
"""

import pytest

libp2p = pytest.importorskip("libp2p")

import trio  # noqa: E402

from agentic_p2p.agent import Agent  # noqa: E402
from agentic_p2p.config import Settings  # noqa: E402
from agentic_p2p.messages import ErrorMessage, ResultMessage  # noqa: E402
from agentic_p2p.peer import AgentPeer  # noqa: E402
from agentic_p2p.workflow import WorkflowResult  # noqa: E402


class DummyOrchestrator:
    """Stands in for the SeaLion workflow so this test never calls a real
    LLM or a real EtherCalc instance — only the P2P transport is real."""

    async def run(self, task_text: str) -> WorkflowResult:
        assert "inventory" in task_text.lower()
        return WorkflowResult(
            status="completed",
            summary="Task completed. Total inventory value: 3,100,000.",
            sheet="inventory-analysis",
        )


@pytest.mark.trio
async def test_agent_a_to_agent_b_task_result_roundtrip():
    responder_peer = AgentPeer(port=0)
    responder_agent = Agent(responder_peer, orchestrator=DummyOrchestrator(), settings=Settings())

    requester_peer = AgentPeer(port=0)
    requester_agent = Agent(requester_peer, settings=Settings())

    result_box: dict = {}

    async with responder_peer.start(on_stream=responder_agent.on_inbound_stream):
        responder_addr = responder_peer.listen_addresses()[0]

        async with requester_peer.start():
            remote_id = await requester_peer.connect_to_peer(responder_addr)

            with trio.move_on_after(15) as cancel_scope:
                reply = await requester_agent.send_task(
                    remote_id, "Analyze this inventory: Laptop 20 units..."
                )
                result_box["reply"] = reply

            assert not cancel_scope.cancelled_caught, "Task/result exchange timed out"

    reply = result_box["reply"]
    assert isinstance(reply, ResultMessage)
    assert "3,100,000" in reply.summary
    assert reply.sheet == "inventory-analysis"


@pytest.mark.trio
async def test_agent_b_returns_error_message_on_workflow_failure():
    class FailingOrchestrator:
        async def run(self, task_text: str):
            raise RuntimeError("LLM request failed")

    responder_peer = AgentPeer(port=0)
    responder_agent = Agent(responder_peer, orchestrator=FailingOrchestrator(), settings=Settings())

    requester_peer = AgentPeer(port=0)
    requester_agent = Agent(requester_peer, settings=Settings())

    result_box: dict = {}

    async with responder_peer.start(on_stream=responder_agent.on_inbound_stream):
        responder_addr = responder_peer.listen_addresses()[0]

        async with requester_peer.start():
            remote_id = await requester_peer.connect_to_peer(responder_addr)

            with trio.move_on_after(15) as cancel_scope:
                reply = await requester_agent.send_task(remote_id, "Analyze this inventory")
                result_box["reply"] = reply

            assert not cancel_scope.cancelled_caught, "Task/result exchange timed out"

    reply = result_box["reply"]
    assert isinstance(reply, ErrorMessage)
    assert "LLM request failed" in reply.error
