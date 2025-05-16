from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_NAME,
    MAX_TOKENS,
    MODEL_TEMPERATURE,
)
from langchain_anthropic import ChatAnthropic


class AnthropicModelHandler:
    def __init__(self):
        self.llm = ChatAnthropic(
            model=ANTHROPIC_MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )
