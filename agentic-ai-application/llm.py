import asyncio

import trio
from litellm import acompletion

from .config import LLM_TIMEOUT, OLLAMA_API_BASE


class LiteLLMClient:
    def __init__(self, model):
        self.model = model

    async def complete(self, messages, temperature=0.2):
        async def call():
            response = await acompletion(
                model=f"ollama/{self.model}",
                messages=messages,
                temperature=temperature,
                api_base=OLLAMA_API_BASE,
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("LLM returned an empty response.")

            return content.strip()

        with trio.move_on_after(LLM_TIMEOUT) as scope:
            result = await trio.to_thread.run_sync(
                lambda: asyncio.run(call())
            )

        if scope.cancelled_caught:
            raise TimeoutError("LLM request timed out.")

        return result
