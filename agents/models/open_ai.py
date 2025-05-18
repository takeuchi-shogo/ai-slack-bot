from config.model import (
    MAX_TOKENS,
    MODEL_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
)
from langchain_openai import ChatOpenAI


class OpenAIModelHandler:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            openai_api_key=OPENAI_API_KEY,
        )
