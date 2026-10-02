import asyncio
from libp2p import new_host
from litellm import completion
import requests
import json

class AgenticP2PNode:
    def __init__(self, host_port=0, llm_model="gpt-3.5-turbo", ethercalc_url=None):
        self.host_port = host_port
        self.llm_model = llm_model
        self.ethercalc_url = ethercalc_url
        self.host = None

    async def start(self):
        # Inicializa o host py-libp2p
        self.host = await new_host(port=self.host_port)
        print(f"Agent Node started on {self.host.get_multiaddress()}")
        
        # Inicia o listener de mensagens (simulado via stream handler)
        # Em py-libp2p, definimos handlers para protocolos específicos
        self.host.set_stream_handler("ai-agent-protocol", self.handle_agent_message)
        
        await asyncio.Future() # Mantém o node rodando

    async def handle_agent_message(self, stream):
        # Lê a mensagem do peer
        data = await stream.read()
        prompt = data.decode('utf-8')
        print(f"Received prompt: {prompt}")

        # 1. Processamento via LiteLLM (Reasoning)
        response = self.reason(prompt)
        
        # 2. Log no EtherCalc (Collaboration)
        if self.ethercalc_url:
            self.log_to_ethercalc(prompt, response)

        # 3. Resposta ao Peer
        await stream.write(f"Agent Response: {response}".encode('utf-8'))
        await stream.close()

    def reason(self, prompt):
        try:
            # Integração LiteLLM
            res = completion(model=self.llm_model, messages=[{"content": prompt, "role": "user"}])
            return res.choices[0].message.content
        except Exception as e:
            return f"Error in reasoning: {str(e)}"

    def log_to_ethercalc(self, prompt, response):
        # EtherCalc usa uma API simples de POST/GET para atualizar células
        # Exemplo simplificado de integração via API REST do EtherCalc
        try:
            payload = {"prompt": prompt, "response": response}
            requests.post(f"{self.ethercalc_url}/api/update", data=payload, timeout=2)
            print("Logged to EtherCalc successfully.")
        except Exception as e:
            print(f"EtherCalc logging failed: {e}")

    async def send_task(self, peer_addr, prompt):
        # Conecta a outro agente e envia um prompt
        conn = await self.host.connect(peer_addr)
        stream = await self.host.new_stream(conn, "ai-agent-protocol")
        await stream.write(prompt.encode('utf-8'))
        response = await stream.read()
        print(f"Peer replied: {response.decode('utf-8')}")
        await stream.close()

if __name__ == "__main__":
    # Exemplo de execução
    node = AgenticP2PNode(ethercalc_url="http://localhost:8000")
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        pass
