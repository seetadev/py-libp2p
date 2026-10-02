import asyncio
from agent_node import AgenticP2PNode

async def main():
    # Node A: O Orquestrador
    node_a = AgenticP2PNode(host_port=10001)
    # Node B: O Worker
    node_b = AgenticP2PNode(host_port=10002, llm_model="gpt-3.5-turbo")

    # Inicia os hosts (em tasks separadas)
    task_a = asyncio.create_task(node_a.start())
    task_b = asyncio.create_task(node_b.start())
    
    await asyncio.sleep(2) # Aguarda boot

    # Node A envia tarefa para Node B
    peer_b_addr = node_b.host.get_multiaddress()
    await node_a.send_task(peer_b_addr, "Analyze the current state of decentralized AI and summarize in one sentence.")

if __name__ == "__main__":
    asyncio.run(main())
