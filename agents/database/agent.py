"""
データベースエージェントモジュール

LLMとデータベースクエリを統合し、自然言語でのデータベース問い合わせを実現します。
LangChainのAgentを使用して、必要に応じてSQLを生成・実行します。
"""

import logging
from typing import Dict

from database.connection import DatabaseConnection
from database.query import NaturalLanguageQueryProcessor
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class DatabaseQueryAgent:
    """
    自然言語でデータベースに問い合わせを行うエージェント

    自然言語でのクエリを受け取り、適切なSQLを生成して実行し、
    結果を人間が理解しやすい形式で返します。
    """

    def __init__(self, llm, db_connection: DatabaseConnection = None):
        """
        DatabaseQueryAgentの初期化

        Args:
            llm: 使用するLLM（AnthropicやGeminiのインスタンス）
            db_connection: データベース接続インスタンス（Noneの場合は新規作成）
        """
        self.llm = llm
        self.db_connection = db_connection or DatabaseConnection()
        self.nl_processor = None
        self._initialized = False

    async def initialize(self) -> None:
        """エージェントを初期化"""
        if not self._initialized:
            # データベース接続を確立
            if (
                not hasattr(self.db_connection, "_connection")
                or self.db_connection._connection is None
            ):
                await self.db_connection.connect()

            # 自然言語クエリプロセッサを初期化
            self.nl_processor = NaturalLanguageQueryProcessor(self.db_connection)
            await self.nl_processor.initialize()

            self._initialized = True
            logger.info("データベースクエリエージェントが初期化されました")

    async def process_query(self, query: str) -> Dict:
        """
        自然言語クエリを処理し、データベースから情報を取得

        Args:
            query: 自然言語のクエリ（例: "アクティブなプロジェクト数はいくつですか？"）

        Returns:
            Dict: 処理結果（クエリ、SQL、結果、説明などを含む）
        """
        if not self._initialized:
            await self.initialize()

        try:
            # クエリがデータベース関連かどうかを判断
            is_db_query = await self.is_database_query(query)

            if is_db_query:
                # データベースクエリとして処理
                logger.info(f"データベースクエリと判断されました: {query}")
                result = await self.nl_processor.process_query(query)

                # 処理情報を追加
                result["query_type"] = "database"
                result["original_query"] = query

                return result
            else:
                # データベースクエリではないと判断
                logger.info(f"非データベースクエリと判断されました: {query}")
                return {
                    "query_type": "non_database",
                    "original_query": query,
                    "explanation": "このクエリはデータベース検索ではないと判断されました。他の方法で処理してください。",
                }

        except Exception as e:
            logger.error(f"クエリ処理エラー: {str(e)}")
            return {
                "query_type": "error",
                "original_query": query,
                "error": str(e),
                "explanation": f"クエリの処理中にエラーが発生しました: {str(e)}",
            }

    async def is_database_query(self, query: str) -> bool:
        """
        クエリがデータベース関連かどうかを判断

        Args:
            query: 自然言語クエリ

        Returns:
            bool: データベース関連のクエリならTrue、そうでなければFalse
        """
        # データベースのスキーマ情報を取得
        schema_info = self.db_connection._generate_schema_info()

        # 判断用のプロンプト
        decider_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=f"""あなたはユーザークエリを分析し、それがデータベース検索かどうかを判断する専門家です。
以下のデータベース情報があります:

{schema_info}

ユーザーの質問がこのデータベースに関連する検索やクエリであるかどうかを判断してください。
データの取得や集計、フィルタリング、検索などのデータベース操作に関する質問の場合は「データベースクエリ」と判断してください。
一般的な質問、会話、データベースと無関係な指示などの場合は「非データベースクエリ」と判断してください。

回答は「データベースクエリ」または「非データベースクエリ」のみにしてください。
"""
                ),
                HumanMessage(content=f"ユーザーの質問: {query}"),
            ]
        )

        # LLMに判断させる
        chain = decider_prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})

        return "データベースクエリ" in result

    async def close(self) -> None:
        """リソースをクリーンアップする"""
        if self.nl_processor:
            await self.nl_processor.close()
        logger.info("データベースクエリエージェントのリソースを解放しました")
