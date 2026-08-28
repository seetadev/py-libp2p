import pytest

from agentic_p2p.agent import Agent
from agentic_p2p.config import Settings
from agentic_p2p.messages import ErrorMessage, ResultMessage, TaskMessage
from agentic_p2p.workflow import WorkflowResult, _LocalOrchestrator, _build_sheet_rows


class DummyPeer:
    peer_id = "peer-b-id"


class DummyOrchestrator:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.received_tasks = []

    async def run(self, task_text):
        self.received_tasks.append(task_text)
        if self._error:
            raise self._error
        return self._result


# ---------------------------------------------------------------------
# Agent-level tests (workflow mocked out entirely)
# ---------------------------------------------------------------------

async def test_handle_task_returns_result_message_on_success():
    orchestrator = DummyOrchestrator(
        result=WorkflowResult(status="completed", summary="All good", sheet="demo")
    )
    agent = Agent(DummyPeer(), orchestrator=orchestrator, settings=Settings())

    task = TaskMessage(task_id="t1", sender="peer-a", task="Analyze this")
    reply = await agent.handle_task(task)

    assert isinstance(reply, ResultMessage)
    assert reply.summary == "All good"
    assert reply.sheet == "demo"
    assert orchestrator.received_tasks == ["Analyze this"]


async def test_handle_task_returns_error_message_on_workflow_failure():
    orchestrator = DummyOrchestrator(error=RuntimeError("LLM request failed"))
    agent = Agent(DummyPeer(), orchestrator=orchestrator, settings=Settings())

    task = TaskMessage(task_id="t2", sender="peer-a", task="Analyze this")
    reply = await agent.handle_task(task)

    assert isinstance(reply, ErrorMessage)
    assert "LLM request failed" in reply.error
    assert reply.task_id == "t2"


# ---------------------------------------------------------------------
# Workflow-level tests (LLM + EtherCalc mocked, orchestrator itself is real)
# ---------------------------------------------------------------------

FAKE_ANALYSIS = {
    "headers": ["Product", "Units", "Unit Price", "Total"],
    "rows": [["Laptop", 20, 60000, 1200000], ["Phone", 50, 20000, 1000000]],
    "totals": {"label": "TOTAL", "value": 2200000},
    "top_performer": {"name": "Laptop", "reason": "highest total value"},
    "recommendations": ["Stock more laptops", "Discount phones", "Bundle accessories"],
}


class FakeEtherCalcClient:
    def __init__(self, *args, **kwargs):
        self.written = None

    async def create_sheet(self, sheet):
        pass

    async def write_cells(self, sheet, rows):
        self.written = rows

    async def read_sheet(self, sheet):
        return self.written or []


@pytest.fixture
def patched_workflow(monkeypatch):
    from agentic_p2p import workflow as workflow_module

    async def fake_generate_json(prompt, *, system=None, settings=None):
        if system == workflow_module.prompts.PLANNER_SYSTEM_PROMPT:
            return {"needs_table": True, "operations": ["analyze"], "notes": ""}
        return FAKE_ANALYSIS

    async def fake_generate_response(prompt, *, system=None, json_mode=False, settings=None):
        return "Task completed. Top product: Laptop. Total: 2,200,000."

    monkeypatch.setattr(workflow_module.llm, "generate_json", fake_generate_json)
    monkeypatch.setattr(workflow_module.llm, "generate_response", fake_generate_response)
    monkeypatch.setattr(workflow_module, "EtherCalcClient", FakeEtherCalcClient)
    return workflow_module


async def test_local_orchestrator_happy_path(patched_workflow):
    orchestrator = patched_workflow._LocalOrchestrator(Settings())
    result = await orchestrator.run("Analyze this inventory")

    assert result.status == "completed"
    assert "Laptop" in result.summary
    assert result.sheet == Settings().ethercalc_sheet
    assert result.warnings == []
    assert result.analysis == FAKE_ANALYSIS


async def test_local_orchestrator_rejects_empty_task(patched_workflow):
    orchestrator = patched_workflow._LocalOrchestrator(Settings())
    with pytest.raises(ValueError):
        await orchestrator.run("   ")


def test_build_sheet_rows_includes_totals_and_recommendations():
    rows = _build_sheet_rows(FAKE_ANALYSIS)
    assert rows[0] == ["Product", "Units", "Unit Price", "Total", "Recommendation"]
    assert rows[1] == ["Laptop", 20, 60000, 1200000, "Stock more laptops"]
    assert rows[-1][0] == "TOTAL"
    assert rows[-1][-1] == 2200000
