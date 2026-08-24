import asyncio
import csv
import io
import json
import logging
import struct
import time
import uuid
from dataclasses import dataclass

import httpx
import multiaddr
import trio
from litellm import acompletion
from libp2p import new_host
from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.peer.peerinfo import info_from_p2p_addr

PROTOCOL_ID = "/sea-lion-multi-agent/1.0.0"

AGENT1_ID = "agent1"
AGENT2_ID = "agent2"
AGENT3_ID = "agent3"


AGENT1_NAME = "Agent-1"
AGENT2_NAME = "Agent-2"
AGENT3_NAME = "Agent-3"

AGENT1_PORT = 9101
AGENT2_PORT = 9102
AGENT3_PORT = 9103

ORCHESTRATOR_MODEL = "aisingapore/Llama-SEA-LION-v3.5-8B-R:latest"

AGENT_MODEL = "gemma3:1b"

OLLAMA_API_BASE = "http://127.0.0.1:11434"

ETHERCALC_BASE_URL = "http://127.0.0.1:8000"
ETHERCALC_ROOM = "sea-lion-agent-collaboration"

LLM_TIMEOUT = 180
P2P_TIMEOUT = 120
CONNECTION_TIMEOUT = 20
MAX_ORCHESTRATION_TURNS = 6
MAX_FRAME_SIZE = 4 * 1024 * 1024

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format=("%(asctime)s " "[%(levelname)s] " "%(name)s: %(message)s"),)

logging.getLogger("LiteLLM").setLevel(logging.WARNING)

@dataclass
class AgentPersona:
    agent_id: str
    name: str
    system_prompt: str


AGENT1 = AgentPersona(
    AGENT1_ID,
    AGENT1_NAME,
    "You are the risk-analysis agent. "
    "Only identify risks, assumptions, weaknesses, "
    "edge cases, vulnerabilities, and failure modes. "

)
AGENT2 = AgentPersona(
    AGENT2_ID,
    AGENT2_NAME,
    "You are the implementation agent. "
    "Convert Agent 1's identified risks into practical "
    "implementation solutions and trade-offs. "
    
)

AGENT3 = AgentPersona(
    AGENT3_ID,
    AGENT3_NAME,
    "You are the validation agent. "
    "Review the proposed risks and implementation solutions. "
    "Identify inconsistencies, missing requirements, and "
    "whether the final solution satisfies the objective."
)

PERSONAS = {
    AGENT1_ID: AGENT1,
    AGENT2_ID: AGENT2,
    AGENT3_ID: AGENT3,
}

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
        

class LiteLLMClient:

    def __init__(self, model):
        self.model = model

    async def complete(self, messages, temperature=0.2):
       

        async def call():

            print(f"LLM: sending request to Ollama: {self.model}",)

            response = await acompletion(
                model=f"ollama/{self.model}",
                messages=messages,
                temperature=temperature,
                api_base=OLLAMA_API_BASE,
            )
            print(f"LLM: received response from Ollama: {self.model}")

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("LLM returned an empty response.")

            return content.strip()

        with trio.move_on_after(LLM_TIMEOUT) as scope:
            result = await trio.to_thread.run_sync(lambda: asyncio.run(call()))

        if scope.cancelled_caught:
            raise TimeoutError("LLM request timed out.")

        return result

class SeaLionOrchestrator:
    def __init__( self, llm, states):
        
        self.llm = llm
        self.states = states
        
    async def choose_next_agent(self, turn):

        history_items = []
    
        for agent_id, state in self.states.items():
            history_items.extend(await state.recent(20))   
    
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
            stage = "Agent 1 must perform the risk analysis."
    
        elif not agent2_done:
            stage = "Agent 2 must propose implementation solutions ""based on Agent 1's risk analysis."
    
        elif not agent3_done:
            stage = "Agent 3 must validate the risks and implementation ""solutions proposed by Agents 1 and 2."
    
        else:
            stage = "The three-agent workflow is complete. " "Choose done." 
    
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
    
            "Do not repeatedly select an agent whose required work "
            "is already complete.\n\n"
    
            "Return ONLY one of these exact values:\n"
            "agent1\n"
            "agent2\n"
            "agent3\n"
            "done"
        )
    
        decision = await self.llm.complete([
                {
                    "role": "system",
                    "content": (
                        "You are a simple and deterministic "
                        "multi-agent routing controller."),
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
    
        raise ValueError(f"SEA-LION returned an invalid routing decision: {decision}")

class EtherCalc:
    def __init__(self, base_url, room):
        self.base_url = base_url.rstrip("/")
        self.room_url = f"{self.base_url}/_/{room}"
    
    async def append(self, operation, turn=None, request=""):
        row = io.StringIO()
    
        csv.writer(row, lineterminator="\n").writerow([
            turn,
            operation["agent_name"],
            operation["role"],
            request,
            operation["content"],
        ])
    
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self.room_url, content=row.getvalue(), headers={"Content-Type": "text/csv"},)
    
            response.raise_for_status()
              
            print(f"EtherCalc: saved turn {turn} - " f"{operation['agent_name']}")
    
        except Exception as exc:
   
            print("EtherCalc error:", exc)


async def read_exact(stream, size):
    data = bytearray()

    while len(data) < size:
        chunk = await stream.read(size - len(data))
        if not chunk:
            raise ConnectionError("Peer closed the stream.")
        data.extend(chunk)

    return bytes(data)


async def send_frame(stream, message):
    payload = json.dumps(message, ensure_ascii=False).encode()

    if len(payload) > MAX_FRAME_SIZE:
        raise ValueError("P2P frame too large.")

    await stream.write(struct.pack("!I", len(payload)) + payload)


async def receive_frame(stream):
    size = struct.unpack("!I", await read_exact(stream, 4))[0]

    if not 0 < size <= MAX_FRAME_SIZE:
        raise ValueError("Invalid P2P frame size.")

    message = json.loads((await read_exact(stream, size)).decode())

    if not isinstance(message, dict):
        raise ValueError("P2P message must be an object.")

    return message


async def generate_worker_response(persona, llm, state, instruction):

    history = await state.recent(12)

    messages = [
        {
            "role": "system",
            "content": persona.system_prompt,
        }
    ]

    messages += [
        {
            "role": "user",
            "content": (
                f"{item['agent_name']} [{item['role']}]:\n"
                f"{item['content']}"
            ),
        }
        for item in history
    ]

    messages.append({
        "role": "user",
        "content": instruction,
    })

    response = await llm.complete(messages, temperature=0.3,)

    return await state.add(
        agent_id=persona.agent_id,
        agent_name=persona.name,
        role="agent",
        content=response,
    )

class P2PNetwork:
    def __init__(self, hosts):
        self.hosts = hosts

    async def open_stream(self, source_id, target_id):
        source = self.hosts[source_id]
        target = self.hosts[target_id]

        address = multiaddr.Multiaddr(f"{get_tcp_address(target)}/p2p/{target.get_id()}")

        info = info_from_p2p_addr(address)

        with trio.move_on_after(CONNECTION_TIMEOUT) as scope:
            await source.connect(info)
            stream = await source.new_stream(target.get_id(), [PROTOCOL_ID],)

        if scope.cancelled_caught:
            
            raise TimeoutError(f"P2P connection failed: {source_id} -> {target_id}")

        return stream

async def handle_incoming_request( stream, local_agent, state, llm, ethercalc,):
    try:
        message = await receive_frame(stream)

        if message.get("type") == "state_sync":
            operation = message.get("operation")

            if not isinstance(operation, dict):
                raise ValueError("Missing operation.")

            await state.merge(operation)

            await send_frame(
                stream,
                {
                    "type": "sync_ack",
                    "agent": local_agent.agent_id,
                },
            )
            return
        if message.get("type") != "agent_request":
            raise ValueError("Expected agent_request.")

        source_agent = message.get("source_agent")
        target_agent = message.get("target_agent")
        operation = message.get("operation")

        if source_agent not in PERSONAS:
            raise ValueError(f"Unknown source agent: {source_agent}")

        if target_agent != local_agent.agent_id:
            raise ValueError("Request sent to wrong agent.")

        if not isinstance(operation, dict):
            raise ValueError("Missing operation.")

        await state.merge(operation)

        response = await generate_worker_response(
            persona=local_agent,
            llm=llm,
            state=state,
            instruction=(
                f"You received a request from {operation['agent_name']}.\n\n"
                f"REQUEST:\n{operation['content']}\n\n"
                "Analyze the request, then provide a concise summary of your result suitable for sending back to the requesting agent."
            ),
        )
        await ethercalc.append(response, request=operation["content"],)

        await send_frame(
            stream,
            {
                "type": "agent_response",
                "request_id": message.get("request_id"),
                "source_agent": local_agent.agent_id,
                "target_agent": source_agent,
                "operation": response,
            },
        )        
    except Exception as exc:
        logger.exception("Incoming P2P request failed.")

        try:
            await send_frame(
                stream,
                {
                    "type": "error",
                    "agent": local_agent.agent_id,
                    "content": f"{type(exc).__name__}: {exc}",
                },
            )
        except Exception:
            pass

    finally:
        await stream.close()#        


async def send_agent_request(network, source_id, target_id, prompt, state):

    source = PERSONAS[source_id]

    operation = await state.add(
        agent_id=source.agent_id,
        agent_name=source.name,
        role="request",
        content=prompt,
    )

    stream = await network.open_stream(source_id, target_id)

    try:
        await send_frame(
            stream,
            {
                "type": "agent_request",
                "request_id": str(uuid.uuid4()),
                "source_agent": source_id,
                "target_agent": target_id,
                "operation": operation,
            },
        )
        with trio.move_on_after(P2P_TIMEOUT) as scope:
            response = await receive_frame(stream)

        if scope.cancelled_caught:
            raise TimeoutError("P2P response timed out.")

        if response.get("type") == "error":
            
            raise RuntimeError(response.get("content", "Remote agent failed."))

        if response.get("type") != "agent_response":
            raise RuntimeError(f"Unexpected response: {response.get('type')}")

        result = response["operation"]

        await state.merge(result)
       
        return result

    finally:
        await stream.close()

async def send_agent_operation(network, source_id, target_id, operation,):
    
    stream = await network.open_stream(source_id, target_id)

    try:
        await send_frame(
            stream,
            {
                "type": "state_sync",
              
                "operation": operation,
            },
        )

        with trio.move_on_after(P2P_TIMEOUT) as scope:
            response = await receive_frame(stream)

        if scope.cancelled_caught:
            raise TimeoutError("P2P synchronization timed out.")

        if response.get("type") != "sync_ack":
            raise RuntimeError(f"Unexpected synchronization response: " f"{response.get('type')}")

    finally:
        await stream.close()

def create_agent_host(persona, state, llm, ethercalc,):
    host = new_host(
        key_pair=create_new_key_pair(),
        enable_tcp=True,
        enable_quic=False,
    )

    async def handler(stream):
        await handle_incoming_request(stream, persona, state, llm, ethercalc)

    host.set_stream_handler(PROTOCOL_ID, handler)

    return host

def get_tcp_address(host):
    for address in host.get_addrs():
        if "/tcp/" in str(address):
            return multiaddr.Multiaddr(str(address))

    raise RuntimeError("No TCP address available.")

async def run_sealion_orchestration( objective, orchestrator, network, states, ethercalc, agent_llms,): 

    print("\n" + "=" * 70)
    print("SEA-LION MULTI-AGENT ORCHESTRATION")
    print("=" * 70)
    print(f"\nObjective:\n{objective}\n")

    operation = await states[AGENT1_ID].add(
        "sealion-orchestrator",
        "SEA-LION Orchestrator",
        "objective",
        objective,
    )

    for agent_id in PERSONAS:
        if agent_id != AGENT1_ID:
            await states[agent_id].merge(operation)


    for turn in range(1, MAX_ORCHESTRATION_TURNS + 1):

        print(f"\n{'-' * 70}")
        print(f"TURN {turn}")
        print("-" * 70)

        print("SEA-LION: deciding next agent...")


        agent_id = await orchestrator.choose_next_agent(turn)

        print(f"SEA-LION selected: {agent_id}")


        if agent_id == "done":
            print("SEA-LION: orchestration complete.")
            break

        if agent_id not in PERSONAS:
            print(f"Invalid agent selection: {agent_id}")
            break

        persona = PERSONAS[agent_id]

        print(f"\n{persona.name}: generating response...")

        instruction = (f"You are {persona.name}.\n\n" f"OBJECTIVE:\n{objective}\n\n")

        if agent_id == AGENT1_ID:
        
            if turn == 1:
                instruction += (
                    "\n\nSTRICT OUTPUT RULES:\n"
                    "You are ONLY Agent 1, the risk-analysis agent.\n"
                    "Your response MUST contain ONLY:\n"
                    "1. Risks\n"
                    "2. Assumptions\n"
                    "3. Weaknesses\n"
                    "4. Edge Cases\n"
                    "5. Vulnerabilities\n"
                    "6. Failure Modes\n"
                )
            else:
                instruction += (
                    "\n\nThis is a review turn.\n\n"
                   
                    "Review Agent 2's implementation proposals above.\n\n"
                    "Identify:\n"
                    "- remaining risks\n"
                    "- weaknesses\n"
                    "- gaps\n"
                    "- unaddressed failure modes\n"
                    "- incorrect assumptions\n"
                    "- security concerns\n"
                    "- reliability concerns\n\n"
                )
        elif agent_id == AGENT2_ID:
        
            instruction += (
                "\n\n"
                "STRICT ROLE: AGENT 2 — IMPLEMENTATION SOLUTIONS ONLY.\n\n"
                "Review Agent 1's risk analysis and propose practical "
                "implementation solutions and trade-offs.\n\n"
                "Do not perform a new risk analysis. Focus only on "
                "implementation solutions."
            )

        elif agent_id == AGENT3_ID:
        
            instruction += (
                "\n\n"
                "STRICT ROLE: AGENT 3 — VALIDATION ONLY.\n\n"
                "Review the previous contributions from Agent 1 and Agent 2.\n\n"
                "Validate the proposed solution.\n\n"
                "Identify:\n"
                "- inconsistencies\n"
                "- missing requirements\n"
                "- unresolved risks\n"
                "- incorrect implementation assumptions\n"
                "- remaining weaknesses\n"
                "- whether the solution satisfies the objective\n"
            )
                        
        operation = await generate_worker_response(
            persona=persona,
            llm=agent_llms[agent_id],
            state=states[agent_id],
            instruction=instruction,
        )

        print(f"\n{persona.name}:")

        print(operation["content"] )

        await ethercalc.append(operation, turn=turn, request=instruction,)

        for target_id in PERSONAS:
            if target_id != agent_id:
                print(f"\nP2P: synchronizing " f"{persona.name} → {PERSONAS[target_id].name}...")
        
                await send_agent_operation(network, agent_id, target_id, operation,)
        
        print("P2P: synchronization complete.")

    print("\n" + "=" * 70)
    print("ORCHESTRATION FINISHED")
    print("=" * 70 + "\n")

async def main():
 
    states = { AGENT1_ID: SharedState(), AGENT2_ID: SharedState(), AGENT3_ID: SharedState(),}

    ethercalc = EtherCalc(ETHERCALC_BASE_URL, ETHERCALC_ROOM,)

    sealion_llm = LiteLLMClient(ORCHESTRATOR_MODEL)
    
    agent_llm = LiteLLMClient(AGENT_MODEL)

    agent_llms = {AGENT1_ID: agent_llm, AGENT2_ID: agent_llm, AGENT3_ID: agent_llm,}

    orchestrator = SeaLionOrchestrator(sealion_llm, states,)

    agent1_host = create_agent_host(AGENT1, states[AGENT1_ID], agent_llm, ethercalc,)

    agent2_host = create_agent_host(AGENT2, states[AGENT2_ID], agent_llm, ethercalc,)

    agent3_host = create_agent_host(AGENT3, states[AGENT3_ID], agent_llm, ethercalc,)

    agent1_address = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{AGENT1_PORT}")

    agent2_address = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{AGENT2_PORT}")
    
    agent3_address = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{AGENT3_PORT}")

    async with (
        agent1_host.run(listen_addrs=[agent1_address]),
        agent2_host.run(listen_addrs=[agent2_address]),

        agent3_host.run(listen_addrs=[agent3_address]),
    ):
        with trio.move_on_after(20) as scope:
            while True:
                try:
                    get_tcp_address(agent1_host)
                    get_tcp_address(agent2_host)
                    get_tcp_address(agent3_host)
                    break
                except RuntimeError:
                    await trio.sleep(0.1)

        if scope.cancelled_caught:
            raise TimeoutError("libp2p nodes failed to start.")

        network = P2PNetwork({AGENT1_ID: agent1_host, AGENT2_ID: agent2_host, AGENT3_ID: agent3_host,})

        print("\n" + "=" * 70)
        print("SAMPLE P2P AGENT TASK")
        print("=" * 70)
        
        sample_prompt = (
            "Analyze the following architecture and identify its main reliability risks: "
            "a decentralized multi-agent system using libp2p, LiteLLM, SEA-LION, "
            "Gemma 3:1B, and EtherCalc."
        )
        
        print(f"\n{AGENT1_NAME} -> {AGENT2_NAME}: sending request...")
        
        sample_response = await send_agent_request(
            network=network,
            source_id=AGENT1_ID,
            target_id=AGENT2_ID,
            prompt=sample_prompt,
            state=states[AGENT1_ID],
            )
        print(f"\n{AGENT2_NAME}: response received")
        print(sample_response["content"])
        
        print("\nSAMPLE P2P TASK COMPLETED")
        print("=" * 70,)

        objective = (
        "Design a reliable decentralized multi-agent architecture "
        "using libp2p, Gemma 3:1B, LiteLLM, and EtherCalc. "
        "Agent 1 should analyze risks, "
        "Agent 2 should propose practical implementation solutions, "
        "and Agent 3 should validate the proposed solution.")
        print("MAIN: objective created")

        print("MAIN: starting SEA-LION orchestration...")   
        
        await run_sealion_orchestration(objective, orchestrator, network, states, ethercalc, agent_llms,)
        print("MAIN: orchestration returned")

    print("MAIN: libp2p hosts stopped")
    print("MAIN: finished")

if __name__ == "__main__":  

    trio.run(main)
