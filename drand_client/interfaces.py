from typing import Protocol, AsyncIterator
from dataclasses import dataclass

@dataclass
class DrandRound:
    round_number: int
    randomness: bytes
    proof: bytes

class DrandTransport(Protocol):
    async def connect(self) -> None:
        ...
    
    async def get_round(self, round_number: int) -> DrandRound:
        ...
    
    async def subscribe_rounds(self) -> AsyncIterator[DrandRound]:
        ...
