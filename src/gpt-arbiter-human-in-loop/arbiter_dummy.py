import random
import asyncio

from arbiter_interface import ArbiterInterface

class ArbiterDummy(ArbiterInterface):
    async def judge(
        self, model: str, prompt: str, 
        max_tokens: int,
    ) -> float:
        await asyncio.sleep(0.5)
        return random.random()
