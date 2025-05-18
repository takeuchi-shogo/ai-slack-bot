import logging

from models.gemini import GeminiModelHandler

from agent.state import State

logger = logging.getLogger(__name__)


class DatabaseAgent:
    """データベースからデータを取得するエージェント"""

    def __init__(self):
        self.model_handler = GeminiModelHandler()
        self.db_connection = None
        self.agent_prompts = None

    async def process_create_sql(self, query: str, state: State) -> str:
        """
        SQLを作成しユーザーに確認する
        ユーザーがOKを返したら、SQLを実行する
        """
        pass

    async def execute(self, query: str, state: State) -> str:
        """
        作成したSQLを実行し、データベースからデータを取得する
        取得できたデータをStateに格納する
        """
        pass
