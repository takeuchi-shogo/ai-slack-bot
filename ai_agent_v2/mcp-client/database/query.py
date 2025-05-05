"""
データベースクエリ処理モジュール

自然言語からSQLを生成し、データベースに問い合わせを実行します。
LangChainのSQL生成チェーンとデータベースユーティリティを使用しています。
"""

import logging
from typing import Dict

from langchain.chains import create_sql_query_chain
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class NaturalLanguageQueryProcessor:
    """
    自然言語のクエリを処理し、データベースから結果を取得するクラス

    LangChainを使用して自然言語→SQL変換と結果取得を行います。
    """

    def __init__(self, db_connection: DatabaseConnection):
        """
        NaturalLanguageQueryProcessorの初期化

        Args:
            db_connection: データベース接続インスタンス
        """
        self.db_connection = db_connection
        self._sql_database = None
        self._query_chain = None
        self._result_formatter_chain = None

    async def initialize(self) -> None:
        """
        LangChainのチェーンを初期化
        データベース接続が行われていない場合は自動的に接続します。
        """
        from config import ANTHROPIC_MODEL_NAME, MODEL_TEMPERATURE
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage

        # データベースに接続
        if (
            not hasattr(self.db_connection, "_langchain_db")
            or self.db_connection._langchain_db is None
        ):
            await self.db_connection.connect()

        # LangChain SQLDatabaseインスタンスを取得
        self._sql_database = self.db_connection.get_langchain_db()

        # SQLクエリ生成用のLLM
        llm = ChatAnthropic(model=ANTHROPIC_MODEL_NAME, temperature=MODEL_TEMPERATURE)

        # SQLクエリ生成チェーン
        self._query_chain = create_sql_query_chain(llm, self._sql_database)

        # 結果整形用のチェーン
        result_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content="""あなたはデータベース検索結果を分かりやすく説明するエキスパートです。
SQLクエリとその実行結果が与えられます。結果を簡潔に日本語で説明してください。
- 結果の概要を最初に述べてください
- 重要なデータや傾向を強調してください
- 技術的なSQLの詳細よりも、結果の意味に焦点を当ててください
- 結果が空の場合は、その理由を推測してください
- 表形式のデータは整形して表示してください
"""
                ),
                HumanMessage(
                    content="""
クエリ: {query}

結果: {result}

上記のクエリと結果に基づいた分析と説明:
"""
                ),
            ]
        )

        self._result_formatter_chain = result_prompt | llm | StrOutputParser()

        logger.info("自然言語クエリプロセッサが初期化されました")

    async def process_query(self, natural_language_query: str) -> Dict:
        """
        自然言語クエリを処理し、結果を返す

        Args:
            natural_language_query: 自然言語のクエリ（例: "すべてのアクティブなプロジェクトを表示して"）

        Returns:
            Dict: 処理結果（SQLクエリ、生データ、説明を含む）
        """
        if self._query_chain is None:
            await self.initialize()

        try:
            # スキーマ情報を取得
            schema_info = self.db_connection.get_schema_info()

            # 自然言語からSQLクエリを生成
            sql_query = await self._query_chain.ainvoke(
                {"question": natural_language_query, "schema": schema_info}
            )

            logger.info(f"生成されたSQLクエリ: {sql_query}")

            # クエリを実行
            raw_result = await self.db_connection.execute_raw_query(sql_query)

            # 結果を整形
            formatted_explanation = await self._result_formatter_chain.ainvoke(
                {"query": sql_query, "result": raw_result}
            )

            return {
                "query": sql_query,
                "raw_result": raw_result,
                "explanation": formatted_explanation,
            }

        except Exception as e:
            logger.error(f"クエリ処理エラー: {str(e)}")
            return {
                "error": str(e),
                "explanation": f"クエリの処理中にエラーが発生しました: {str(e)}",
            }

    async def close(self) -> None:
        """リソースをクリーンアップする"""
        await self.db_connection.disconnect()
        logger.info("自然言語クエリプロセッサが終了しました")
