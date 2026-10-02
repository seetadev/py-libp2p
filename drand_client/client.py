from typing import Optional
from .interfaces import DrandTransport, DrandRound
from .http_transport import HttpTransport

class DrandClient:
    def __init__(self, transport: Optional[DrandTransport] = None):
        self.transport = transport or HttpTransport()

    async def initialize(self):
        await self.transport.connect()

    async def get_randomness(self, round_number: int) -> DrandRound:
        return await self.transport.get_round(round_number)

    async def listen_for_randomness(self):
        async for round_data in self.transport.subscribe_rounds():
            yield round_data
