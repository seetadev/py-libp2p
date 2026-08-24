from .config import (
    AGENT1_ID,
    AGENT2_ID,
    AGENT3_ID,
)


class SeaLionOrchestrator:
    def __init__(self, llm, states, personas):
        self.llm = llm
        self.states = states
        self.personas = personas

    async def choose_next_agent(self, turn):
        history_items = []

        for state in self.states.values():
            history_items.extend(
                await state.recent(20)
            )

        agent1_done = any(
            item["agent_id"] == AGENT1_ID
            and item["role"] == "agent"
            for item in history_items
        )

        agent2_done = any(
            item["agent_id"] == AGENT2_ID
            and item["role"] == "agent"
            for item in history_items
        )

        agent3_done = any(
            item["agent_id"] == AGENT3_ID
            and item["role"] == "agent"
            for item in history_items
        )

        if not agent1_done:
            stage = (
                "Agent 1 must perform the risk analysis."
            )
        elif not agent2_done:
            stage = (
                "Agent 2 must propose implementation "
                "solutions based on Agent 1's risk analysis."
            )
        elif not agent3_done:
            stage = (
                "Agent 3 must validate the risks and "
                "implementation solutions proposed by "
                "Agents 1 and 2."
            )
        else:
            stage = (
                "The three-agent workflow is complete. "
                "Choose done."
            )

        prompt = (
            "You are the SEA-LION orchestration controller.\n\n"
            "Your job is to select the next agent in a "
            "three-agent workflow.\n\n"
            "Available choices:\n"
            "- agent1 = risk analysis\n"
            "- agent2 = implementation solutions\n"
            "- agent3 = validation\n"
            "- done = finish the task\n\n"
            f"Current turn: {turn}\n\n"
            "Workflow state:\n"
            f"- Agent 1 completed: {agent1_done}\n"
            f"- Agent 2 completed: {agent2_done}\n"
            f"- Agent 3 completed: {agent3_done}\n\n"
            f"Required next stage:\n{stage}\n\n"
            "Routing rules:\n"
            "1. If Agent 1 is not complete, choose agent1.\n"
            "2. Otherwise, if Agent 2 is not complete, choose agent2.\n"
            "3. Otherwise, if Agent 3 is not complete, choose agent3.\n"
            "4. Otherwise, choose done.\n\n"
            "Do not repeatedly select an agent whose required "
            "work is already complete.\n\n"
            "Return ONLY one of these exact values:\n"
            "agent1\n"
            "agent2\n"
            "agent3\n"
            "done"
        )

        decision = await self.llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a simple and deterministic "
                        "multi-agent routing controller."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.0,
        )

        decision = decision.strip().lower()

        if "agent1" in decision:
            return AGENT1_ID

        if "agent2" in decision:
            return AGENT2_ID

        if "agent3" in decision:
            return AGENT3_ID

        if "done" in decision:
            return "done"

        raise ValueError(
            "SEA-LION returned an invalid routing decision: "
            f"{decision}"
        )
