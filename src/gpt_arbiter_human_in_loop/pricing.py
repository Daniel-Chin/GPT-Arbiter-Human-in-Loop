'''
Manually update this file to match 
https://openai.com/api/pricing

There is an openai cost api but only for orgs currently.  
'''

from dataclasses import dataclass

from openai.types.completion_usage import CompletionUsage

@dataclass(frozen=True)
class ModelPricing:
    USD_per_1M_tokens_input: float
    USD_per_1M_tokens_input_cached: float
    USD_per_1M_tokens_output: float

    def estimate(self, usage: CompletionUsage | None) -> float:
        if usage is None:
            return 0.0
        i, o = (
            usage.prompt_tokens, 
            usage.completion_tokens,
        )
        details = usage.prompt_tokens_details
        if details is None:
            cached = 0
        else:
            cached = details.cached_tokens or 0
        non_cached = i - cached
        return (
            non_cached * self.USD_per_1M_tokens_input + 
            cached     * self.USD_per_1M_tokens_input_cached + 
            o          * self.USD_per_1M_tokens_output
        ) / 1000_000

PRICING = {
    'gpt-5': ModelPricing(
        USD_per_1M_tokens_input=1.250,
        USD_per_1M_tokens_input_cached=0.125,
        USD_per_1M_tokens_output=10.000,
    ),
    'gpt-5-mini': ModelPricing(
        USD_per_1M_tokens_input=0.250,
        USD_per_1M_tokens_input_cached=0.025,
        USD_per_1M_tokens_output=2.000,
    ),
    'gpt-5-nano': ModelPricing(
        USD_per_1M_tokens_input=0.050,
        USD_per_1M_tokens_input_cached=0.005,
        USD_per_1M_tokens_output=0.400,
    ),
    'gpt-4o-mini': ModelPricing(
        USD_per_1M_tokens_input=0.150,
        USD_per_1M_tokens_input_cached=0.075,
        USD_per_1M_tokens_output=0.600,
    ),
}
