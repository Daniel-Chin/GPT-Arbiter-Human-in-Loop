from datetime import timedelta

import numpy as np
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletion
from cachier import cachier

from gpt_auto_retry import callWithAutoRetry

class Arbiter:
    def __init__(
        self, 
        client: OpenAI, 
        cache_stale_after: timedelta = timedelta(weeks=6),
    ):
        '''
        `cache_stale_after` can be `timedelta.max` if `model` in `self.judge()` will always point to a specific checkpoint.
        '''
        self.client = client
    
        c = cachier(separate_files=True, stale_after=cache_stale_after)
        j = c(self.judge)
        self.judge = j   # type: ignore
    
    def judge(
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
        def f():
            return self.client.chat.completions.create(
                model=model, 
                messages=history, 
                max_tokens=max_tokens,
                temperature=0,    # should be inconsequential. 
                logprobs=True,
                top_logprobs=5,
            )
        response: ChatCompletion = callWithAutoRetry(f)
        assert isinstance(response, ChatCompletion) # for static type
        choice = response.choices[0]
        lp = choice.logprobs
        assert lp is not None
        c = lp.content
        assert c is not None
        yes, no = 0.0, 0.0
        for top in c[0].top_logprobs:
            prob: float = np.exp(top.logprob)
            if top.token == 'Yes':
                yes = prob
            elif top.token == 'No':
                no = prob
        if yes + no == 0:
            print(f'{c[0].top_logprobs = }')
            assert False
        return yes / (yes + no)
