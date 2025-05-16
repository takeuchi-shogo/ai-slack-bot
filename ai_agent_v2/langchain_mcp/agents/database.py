"""
自然言語データベースクエリを処理するエージェント

このモジュールはデータベースとのやり取りを行うエージェントを提供します。
自然言語クエリからSQLを生成し、データベースに問い合わせを行います。
"""

import json
import logging
from typing import Any, Dict

from config import get_db_url
from database.agent import DatabaseQueryAgent
from database.connection import DatabaseConnection
from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class DatabaseAgent:
    """データベースクエリを処理するエージェント

    自然言語クエリからSQLを生成し、データベースへの問い合わせを実行する
    エージェントを提供します。LangChainのツールを使用して実装しています。
    """

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.mcp_config = None
        self.db_url = get_db_url()
        self.db_connection = None
        self.db_agent = None

        try:
            with open("mcp_config/database.json", "r") as f:
                self.mcp_config = json.load(f)
        except FileNotFoundError:
            logger.error("Database MCP設定ファイルが見つかりません")
            # デフォルト設定を使用
            self.mcp_config = {"mcpServers": {}}

    async def initialize(self) -> None:
        """エージェントを初期化する"""
        if self.db_agent is None:
            # データベース接続を作成
            self.db_connection = DatabaseConnection()
            # DatabaseQueryAgentを初期化
            self.db_agent = DatabaseQueryAgent(
                self.model_handler.llm, self.db_connection
            )
            await self.db_agent.initialize()
            logger.info("データベースエージェントが初期化されました")

    async def process_query(self, natural_query: str) -> Dict[str, Any]:
        """自然言語クエリを処理してデータベース結果を返す

        Args:
            natural_query: 自然言語クエリ

        Returns:
            処理結果（クエリ、SQL、結果、説明を含む辞書）
        """
        if self.db_agent is None:
            await self.initialize()

        try:
            # データベースエージェントにクエリを処理させる
            result = await self.db_agent.process_query(natural_query)

            # 処理結果をフォーマット
            if "error" in result:
                # エラーがあった場合はエラーメッセージを返す
                return {
                    "query": natural_query,
                    "error": result["error"],
                    "response": f"クエリ実行エラー: {result['error']}",
                }

            # 正常に処理された場合は結果を返す
            return {
                "query": natural_query,
                "sql": result.get("query", ""),
                "result": result.get("raw_result", []),
                "response": result.get("explanation", ""),
            }

        except Exception as e:
            logger.error(f"クエリ処理エラー: {str(e)}")
            return {
                "query": natural_query,
                "error": str(e),
                "response": f"クエリ処理エラー: {str(e)}",
            }

    async def close(self) -> None:
        """リソースをクリーンアップする"""
        if self.db_agent:
            await self.db_agent.close()
            logger.info("データベースエージェントのリソースを解放しました")
