import httpx
from .interfaces import DrandTransport, DrandRound

class HttpTransport(DrandTransport):
    def __init__(self, endpoint: str = "https://api.drand.sh"):
        self.endpoint = endpoint

    async def connect(self) -> None:
        pass

    async def get_round(self, round_number: int) -> DrandRound:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.endpoint}/rounds/{round_number}")
            response.raise_for_status()
            data = response.json()
            return DrandRound(
                round_number=data['round'],
                randomness=bytes.fromhex(data['randomness']),
                proof=bytes.fromhex(data['proof'])
            )

    async def subscribe_rounds(self):
        raise NotImplementedError("HTTP Transport does not support native pubsub subscriptions.")
