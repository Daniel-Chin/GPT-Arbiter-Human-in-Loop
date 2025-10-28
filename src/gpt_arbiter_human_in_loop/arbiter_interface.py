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
    def getRunningCost(self) -> float:
        '''
        Returns the total cost incurred so far in USD.
        '''
        raise NotImplementedError
