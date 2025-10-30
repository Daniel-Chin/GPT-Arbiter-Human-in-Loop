import typing as tp
import random
import asyncio

from .arbiter_interface import ArbiterInterface

class ArbiterDummy(ArbiterInterface):
    async def judge(
        self, model: str, prompt: str, 
        max_tokens: int,
    ) -> float:
        await asyncio.sleep(0.1)
        return random.random()
    
    async def interrogate(
        self, model: str, prompt: str, 
        callbackNo:  tp.Callable[[str], None],
        callbackYes: tp.Callable[[str], None],
        max_tokens: int,
        question: str,
    ) -> None:
        callbackYes("Because I said so.")

    def getRunningCost(self) -> float:
        return 0.0
    
    def getCostPerItem(self) -> float:
        return 0.0
