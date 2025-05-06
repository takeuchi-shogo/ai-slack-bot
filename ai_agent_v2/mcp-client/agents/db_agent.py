"""
データベースクエリエージェントモジュール

自然言語からSQLへの変換と、データベース検索を処理するエージェントを提供します
LangGraphフレームワークに対応
"""

import logging
from typing import Any, Dict, Optional

from config import get_agent_prompts
from database.connection import DatabaseConnection
from database.query import NaturalLanguageQueryProcessor
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class DBQueryAgent:
    """
    データベースクエリエージェント

    自然言語のクエリをSQLに変換してデータベースに問い合わせ、結果を整形します。
    LangGraphのエージェントノードとして機能します。
    """

    def __init__(
        self,
        llm: Optional[ChatAnthropic] = None,
        db_connection: Optional[DatabaseConnection] = None,
    ):
        """
        DBQueryAgentの初期化

        Args:
            llm: 言語モデル
            db_connection: データベース接続のインスタンス
        """
        self.llm = llm
        self.db_connection = db_connection
        self.nl_query_processor = None
        self.prompts = get_agent_prompts()

    async def initialize(self):
        """
        エージェントを初期化

        必要なコンポーネントを初期化し、接続を確立します
        """
        if not self.db_connection:
            self.db_connection = DatabaseConnection()
            await self.db_connection.connect()

        if not self.nl_query_processor:
            self.nl_query_processor = NaturalLanguageQueryProcessor(self.db_connection)
            await self.nl_query_processor.initialize()

        logger.info("DBクエリエージェントが初期化されました")

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        クエリを処理してデータベース結果を返す

        LangGraphのノード関数として機能し、状態を更新します。

        Args:
            state: 現在の状態

        Returns:
            Dict[str, Any]: 更新された状態
        """
        # 必要に応じて初期化
        if not self.nl_query_processor:
            await self.initialize()

        query = state.get("query", "")

        try:
            # データベースクエリを実行
            result = await self.nl_query_processor.process_query(query)

            # プロンプトを使って結果を処理
            if "error" in result:
                error_message = result.get("error", "不明なエラー")
                explanation = result.get("explanation", "詳細情報はありません")

                logger.error(f"データベースクエリ処理エラー: {error_message}")

                # エラー説明の生成
                db_prompt = self.prompts.get("db_query", "")
                messages = [
                    SystemMessage(content=db_prompt),
                    HumanMessage(
                        content=f"次のユーザークエリの処理中にエラーが発生しました：\n\n{query}\n\nエラー：{error_message}\n\n{explanation}\n\nユーザーにわかりやすく説明してください。"
                    ),
                ]

                error_response = await self.llm.ainvoke(messages)
                formatted_result = {
                    "error": error_message,
                    "query": query,
                    "explanation": error_response.content,
                }
            else:
                # 正常な結果
                sql_query = result.get("query", "")
                raw_result = result.get("raw_result", [])
                explanation = result.get("explanation", "")

                logger.info(f"データベースクエリ実行成功: {sql_query}")

                formatted_result = {
                    "query": sql_query,
                    "raw_result": raw_result,
                    "explanation": explanation,
                }

            # 状態を更新
            return {
                "db_result": formatted_result,
                "response": formatted_result.get(
                    "explanation", "データベースからの結果はありません"
                ),
            }

        except Exception as e:
            logger.error(f"DBクエリエージェント処理エラー: {str(e)}")

            # エラー時の状態更新
            return {
                "db_result": {"error": str(e)},
                "response": f"データベースクエリの処理中にエラーが発生しました: {str(e)}",
            }

    async def cleanup(self):
        """リソースのクリーンアップ"""
        if self.nl_query_processor:
            await self.nl_query_processor.close()
