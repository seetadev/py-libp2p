import multiaddr
import trio

from agent import AgentPersona, generate_worker_response
from config import (
    AGENT1_ID,
    AGENT2_ID,
    AGENT3_ID,
    AGENT1_NAME,
    AGENT2_NAME,
    AGENT3_NAME,
    AGENT1_PORT,
    AGENT2_PORT,
    AGENT3_PORT,
    AGENT_MODEL,
    ORCHESTRATOR_MODEL,
    ETHERCALC_BASE_URL,
    ETHERCALC_ROOM,
    MAX_ORCHESTRATION_TURNS,
)
from ethercalc import EtherCalc
from llm import LiteLLMClient
from orchestrator import SeaLionOrchestrator
from p2p_network import (
    P2PNetwork,
    create_agent_host,
    send_agent_request,
    send_agent_operation,
    get_tcp_address,
)
from state import SharedState


PERSONAS = {
    AGENT1_ID: AgentPersona(
        AGENT1_ID,
        AGENT1_NAME,
        "You are the risk-analysis agent. "
        "Only identify risks, assumptions, weaknesses, edge cases, "
        "vulnerabilities, and failure modes.",
    ),
    AGENT2_ID: AgentPersona(
        AGENT2_ID,
        AGENT2_NAME,
        "You are the implementation agent. "
        "Convert Agent 1's identified risks into practical "
        "implementation solutions and trade-offs.",
    ),
    AGENT3_ID: AgentPersona(
        AGENT3_ID,
        AGENT3_NAME,
        "You are the validation agent. "
        "Review the proposed risks and implementation solutions. "
        "Identify inconsistencies, missing requirements, and "
        "whether the final solution satisfies the objective.",
    ),
}

PORTS = {
    AGENT1_ID: AGENT1_PORT,
    AGENT2_ID: AGENT2_PORT,
    AGENT3_ID: AGENT3_PORT,
}


def create_hosts(states, llm, ethercalc):
    return {
        agent_id: create_agent_host(
            PERSONAS[agent_id],
            states[agent_id],
            llm,
            ethercalc,
            PERSONAS,
        )
        for agent_id in PERSONAS
    }


async def wait_for_hosts(hosts):
    with trio.move_on_after(20) as scope:
        while True:
            try:
                for host in hosts.values():
                    get_tcp_address(host)
                return
            except RuntimeError:
                await trio.sleep(0.1)

    if scope.cancelled_caught:
        raise TimeoutError("libp2p nodes failed to start.")


async def run_orchestration(objective, orchestrator, network, states, ethercalc, llm):
    operation = await states[AGENT1_ID].add(
        "sealion-orchestrator",
        "SEA-LION Orchestrator",
        "objective",
        objective,
    )
    print("\n" + "=" * 80)
    print(f"{operation['agent_name']} RESPONSE")
    print("=" * 80)
    print(operation["content"])
    print("=" * 80 + "\n")

    for agent_id in PERSONAS:
        if agent_id != AGENT1_ID:
            await states[agent_id].merge(operation)

    for turn in range(1, MAX_ORCHESTRATION_TURNS + 1):
        agent_id = await orchestrator.choose_next_agent(turn)

        if agent_id == "done":
            break
        if agent_id not in PERSONAS:
            raise ValueError(f"Invalid agent selection: {agent_id}")

        persona = PERSONAS[agent_id]
        instruction = f"You are {persona.name}.\n\nOBJECTIVE:\n{objective}\n\n"

        if agent_id == AGENT1_ID:
            instruction += (
                "STRICT OUTPUT RULES:\n"
                "You are ONLY Agent 1, the risk-analysis agent.\n"
                "Your response MUST contain ONLY:\n"
                "1. Risks\n2. Assumptions\n3. Weaknesses\n"
                "4. Edge Cases\n5. Vulnerabilities\n6. Failure Modes\n"
                if turn == 1 else
                "Review Agent 2's implementation proposals above.\n"
                "Identify remaining risks, weaknesses, gaps, unaddressed "
                "failure modes, incorrect assumptions, security concerns, "
                "and reliability concerns.\n"
            )
        elif agent_id == AGENT2_ID:
            instruction += (
                "STRICT ROLE: AGENT 2 — IMPLEMENTATION SOLUTIONS ONLY.\n"
                "Review Agent 1's risk analysis and propose practical "
                "implementation solutions and trade-offs. Do not perform "
                "a new risk analysis.\n"
            )
        else:
            instruction += (
                "STRICT ROLE: AGENT 3 — VALIDATION ONLY.\n"
                "Review the previous contributions from Agents 1 and 2. "
                "Identify inconsistencies, missing requirements, unresolved "
                "risks, incorrect implementation assumptions, remaining "
                "weaknesses, and whether the solution satisfies the objective.\n"
            )

        operation = await __import__("agent", fromlist=["generate_worker_response"]).generate_worker_response(
            persona, llm, states[agent_id], instruction
        )

        print("\n" + "=" * 80, flush=True)
        print(f"{operation['agent_name']} RESPONSE", flush=True)
        print("=" * 80, flush=True)
        print(operation["content"], flush=True)
        print("=" * 80 + "\n", flush=True)


        await ethercalc.append(operation, turn=turn, request=instruction)

        for target_id in PERSONAS:
            if target_id != agent_id:
                await send_agent_operation(
                    network, agent_id, target_id, operation
                )


async def main():
    states = {agent_id: SharedState() for agent_id in PERSONAS}
    ethercalc = EtherCalc(ETHERCALC_BASE_URL, ETHERCALC_ROOM)

    orchestrator_llm = LiteLLMClient(ORCHESTRATOR_MODEL)
    agent_llm = LiteLLMClient(AGENT_MODEL)
    orchestrator = SeaLionOrchestrator(
        orchestrator_llm, states, PERSONAS
    )

    hosts = create_hosts(states, agent_llm, ethercalc)
    addresses = {
        agent_id: multiaddr.Multiaddr(
            f"/ip4/127.0.0.1/tcp/{PORTS[agent_id]}"
        )
        for agent_id in PERSONAS
    }

    async with (
        hosts[AGENT1_ID].run(listen_addrs=[addresses[AGENT1_ID]]),
        hosts[AGENT2_ID].run(listen_addrs=[addresses[AGENT2_ID]]),
        hosts[AGENT3_ID].run(listen_addrs=[addresses[AGENT3_ID]]),
    ):
        await wait_for_hosts(hosts)

        network = P2PNetwork(hosts)

        objective = (
            "Design a reliable decentralized multi-agent architecture "
            "using libp2p, Gemma 3:1B, LiteLLM, and EtherCalc. "
            "Agent 1 should analyze risks, Agent 2 should propose "
            "practical implementation solutions, and Agent 3 should "
            "validate the proposed solution."
        )
        await run_orchestration(
            objective, orchestrator, network, states, ethercalc, agent_llm
        )



if __name__ == "__main__":
    trio.run(main)
