import os
import logging

import openai
import dotenv
import tenacity

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def initClient():
    decorator = tenacity.retry(
        retry=(
            tenacity.retry_if_exception_type(openai.RateLimitError) |
            tenacity.retry_if_exception_type(openai.InternalServerError)
        ),
        wait=tenacity.wait_exponential_jitter(initial=1, max=30),
        stop=tenacity.stop_after_attempt(6),
        before_sleep=tenacity.before_sleep_log(log, logging.WARNING),
    )

    dotenv.load_dotenv()

    api_Key = os.getenv('OPENAI_API_KEY')

    client = openai.AsyncOpenAI(api_key=api_Key)
    client.chat.completions.create = decorator(client.chat.completions.create)

    return client
