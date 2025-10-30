import typing as tp
from abc import ABC, abstractmethod

class ArbiterInterface(ABC):
    @abstractmethod
    async def judge(
        self, model: str, prompt: str, 
        max_tokens: int,
    ) -> float:
        '''
        `max_tokens` can be larger if you want to debug by knowing what it wants to say.
        '''
        raise NotImplementedError
    
    @abstractmethod
    async def interrogate(
        self, model: str, prompt: str, 
        callbackNo:  tp.Callable[[str], None],
        callbackYes: tp.Callable[[str], None],
        max_tokens: int,
        question: str,
    ) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def getRunningCost(self) -> float:
        '''
        Returns the total cost incurred so far in USD.
        '''
        raise NotImplementedError
    
    @abstractmethod
    def getCostPerItem(self) -> float:
        '''
        Returns the recent cost per item in USD.
        '''
        raise NotImplementedError
