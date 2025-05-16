from config import GEMINI_MODEL_NAME, MAX_TOKENS, MODEL_TEMPERATURE
from langchain_google_genai import ChatGoogleGenerativeAI


class GeminiModelHandler:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
