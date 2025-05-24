import logging
from typing import Any, Dict

from config.database import get_db_url
from database.agent import DatabaseQueryAgent
from database.connection import DatabaseConnection
from database.query import NaturalLanguageQueryProcessor
from models.gemini import GeminiModelHandler

from agent.state import State

logger = logging.getLogger(__name__)


class DatabaseAgent:
    """データベースからデータを取得するエージェント"""

    def __init__(self):
        self.model_handler = GeminiModelHandler()
        self.db_url = get_db_url()
        self.db_connection = None
        self.agent_prompts = None
        self.nl_processor = None
        self.db_agent = None

    async def initialize(self) -> None:
        """エージェントを初期化する"""
        if self.db_agent is None:
            # データベース接続を作成
            self.db_connection = DatabaseConnection()
            # 自然言語クエリプロセッサを初期化
            self.nl_processor = NaturalLanguageQueryProcessor(self.db_connection)
            await self.nl_processor.initialize()
            # DatabaseQueryAgentを初期化
            self.db_agent = DatabaseQueryAgent(
                self.model_handler.llm, self.db_connection
            )
            await self.db_agent.initialize()
            logger.info("データベースエージェントが初期化されました")

    async def process_create_sql(self, query: str, state: State) -> str:
        """
        自然言語クエリを発行し、SQLを作成する
        ユーザーへの確認は必要

        Args:
            query: 自然言語クエリ
            state: エージェントの状態

        Returns:
            処理結果（SQL）
        """
        if self.db_agent is None:
            await self.initialize()

        try:
            # 自然言語からSQLクエリを生成
            sql_query = await self.nl_processor.generate_sql_query(query)

            return sql_query

        except Exception as e:
            logger.error(f"SQLクエリ生成エラー: {str(e)}")
            return None

    async def execute(self, query: str, state: State) -> Dict[str, Any]:
        """
        作成したSQLを実行し、データベースからデータを取得する
        取得できたデータをStateに格納する
        """
        if self.db_agent is None:
            await self.initialize()

        try:
            # データベースエージェントにクエリを処理させる
            result = await self.db_agent.process_query(query)

            # 処理結果をフォーマット
            if "error" in result:
                # エラーがあった場合はエラーメッセージを返す
                return {
                    "query": query,
                    "error": result["error"],
                    "response": f"クエリ実行エラー: {result['error']}",
                }

            # 正常に処理された場合は結果を返す
            return {
                "query": query,
                "sql": result.get("query", ""),
                "result": result.get("raw_result", []),
                "response": result.get("explanation", ""),
            }

        except Exception as e:
            logger.error(f"クエリ処理エラー: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "response": f"クエリ処理エラー: {str(e)}",
            }
