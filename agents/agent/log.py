import logging

from models.gemini import GeminiModelHandler

from agent.state import State

logger = logging.getLogger(__name__)


class LogAgent:
    """
    ログを取得するエージェント

    DataDogからログを取得する
    """

    def __init__(self):
        self.model_handler = GeminiModelHandler()
        self.log_config = None

    async def execute(self, query: str, state: State) -> str:
        """
        ログを取得する
        取得したログをStateに格納する
        """
        pass
