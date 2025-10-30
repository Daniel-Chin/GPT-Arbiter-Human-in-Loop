import asyncio
from datetime import timedelta
import typing as tp

import numpy as np
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam, 
    ChatCompletionAssistantMessageParam,
    ChatCompletion, ChatCompletionChunk, 
    ChatCompletionStreamOptionsParam,
)
from cachier import cachier

from .shared import NO_OR_YES
from .arbiter_interface import ArbiterInterface
from .pricing import PRICING

class ArbiterGPT(ArbiterInterface):
    def __init__(
        self, 
        client: AsyncOpenAI, 
        cache_stale_after: timedelta = timedelta(weeks=6),
    ):
        '''
        `cache_stale_after` can be `timedelta.max` if `model` in `self.judge()` will always point to a specific checkpoint.
        '''
        self.client = client
    
        c = cachier(separate_files=True, stale_after=cache_stale_after)
        j = c(self.judge)
        self.judge = j   # type: ignore

        self.running_cost = 0.0
        self.unit_cost = 0.0
    
    async def judge(
        self, model: str, prompt: str, 
        max_tokens: int = 1,
    ):
        '''
        `max_tokens` can be larger if you want to debug by knowing what it wants to say.
        '''
        history = [ChatCompletionUserMessageParam(
            content=prompt, 
            role='user', 
        )]
        response: ChatCompletion = await self.client.chat.completions.create(
            model=model, 
            messages=history, 
            max_tokens=max_tokens,
            temperature=0,    # should be inconsequential. 
            logprobs=True,
            top_logprobs=5,
        )
        assert isinstance(response, ChatCompletion) # for static type
        self.unit_cost = PRICING[model].estimate(response.usage)
        self.running_cost += self.unit_cost
        choice = response.choices[0]
        lp = choice.logprobs
        assert lp is not None
        c = lp.content
        assert c is not None
        yes, no = 0.0, 0.0
        for top in c[0].top_logprobs:
            prob: float = np.exp(top.logprob)
            if top.token == NO_OR_YES[1]:
                yes = prob
            elif top.token == NO_OR_YES[0]:
                no = prob
        if yes + no == 0:
            print(f'{c[0].top_logprobs = }')
            assert False
        return yes / (yes + no)

    async def interrogate(
        self, model: str, prompt: str, 
        callbackNo:  tp.Callable[[str], None],
        callbackYes: tp.Callable[[str], None],
        max_tokens: int,
        question: str,
    ) -> None:
        async def f(decision: str, callback: tp.Callable[[str], None]) -> None:
            history = [
                ChatCompletionUserMessageParam(
                    content=prompt, 
                    role='user', 
                ),
                ChatCompletionAssistantMessageParam(
                    content=decision,
                    role='assistant',
                ),
                ChatCompletionUserMessageParam(
                    content=question, 
                    role='user', 
                ),
            ]
            async for chunk in await self.client.chat.completions.create(
                model=model, 
                messages=history, 
                max_tokens=max_tokens,
                temperature=1,
                stream=True,
                stream_options=ChatCompletionStreamOptionsParam(
                    include_usage=True,
                ),
            ):
                assert isinstance(chunk, ChatCompletionChunk)
                self.running_cost += PRICING[model].estimate(
                    chunk.usage, # empty except last
                )
                choice = chunk.choices[0]
                callback(choice.delta.content or '')
        
        await asyncio.gather(*[
            f(decision, callback) for decision, callback in zip(NO_OR_YES, (
                callbackNo, 
                callbackYes, 
            ))
        ])

    def getRunningCost(self) -> float:
        return self.running_cost
    
    def getCostPerItem(self) -> float:
        return self.unit_cost

def test():
    client = AsyncOpenAI()
    arbiter = ArbiterGPT(client)
    prompt = "Does lava melt apples?"
    async def main():
        prob = await arbiter.judge(
            model='gpt-4o-mini', 
            prompt=prompt, 
        )
        print(f'Probability of YES: {prob:.4f}')
    asyncio.run(main())
    print(f'Running cost: ${arbiter.getRunningCost():.6f}')
    print(f'Cost per item: ${arbiter.getCostPerItem():.6f}')

if __name__ == '__main__':
    test()
