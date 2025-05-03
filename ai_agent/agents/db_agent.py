import json
import logging
import re
from typing import Any, Dict, Optional

from config import settings
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from models import MentionTask
from services.db_service import DBService

logger = logging.getLogger(__name__)


class DatabaseAgent:
    """データベースエージェント"""

    def __init__(self):
        # LLMの初期化 (Gemini)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=settings.GOOGLE_API_KEY,
        )

        # データベースサービスの初期化
        self.db_service = DBService()

    async def analyze_query(self, sql_query: str) -> Dict[str, Any]:
        """
        SQLクエリを解析する

        Args:
            sql_query: 解析するSQLクエリ

        Returns:
            解析結果（クエリの有効性と修正クエリ）
        """
        try:
            # 解析プロンプト
            prompt = PromptTemplate.from_template(
                """
                あなたはSQLエキスパートです。以下のSQLクエリを分析して、構文エラーや非効率な点を特定してください。

                # SQLクエリ
                ```sql
                {query}
                ```

                # 指示
                1. このSQLクエリが正しく実行できるかどうかを判断してください。
                2. 構文エラーや論理的な問題がある場合は、修正したクエリを提案してください。
                3. クエリが正しい場合は、最適化の余地があるかどうかを検討してください。

                # 出力形式
                以下の形式でJSONとして出力してください:
                ```json
                {{
                  "is_valid": true|false,  // クエリが有効かどうか
                  "error_details": "エラーの詳細説明（エラーがある場合）",
                  "corrected_query": "修正されたSQLクエリ（必要な場合）"
                }}
                ```
                """
            )

            # LLMでクエリを分析
            chain = prompt | self.llm | StrOutputParser()
            analysis_result = await chain.ainvoke({"query": sql_query})

            # JSONを抽出
            json_match = re.search(r"```json\s*(.*?)\s*```", analysis_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSONブロックが見つからない場合は全体をJSONとして解析
                json_str = analysis_result

            # JSON文字列をパース
            result = json.loads(json_str)
            return result

        except Exception as e:
            logger.error(f"Error analyzing SQL query: {e}")
            return {
                "is_valid": False,
                "error_details": f"クエリ分析中にエラーが発生しました: {str(e)}",
                "corrected_query": "",
            }

    async def get_db_schema_info(self) -> Dict[str, Any]:
        """
        データベースのスキーマ情報を取得する

        Returns:
            データベーススキーマ情報
        """
        try:
            # テーブル一覧を取得
            tables_result = await self.db_service.list_tables()

            if not tables_result["success"]:
                return {
                    "success": False,
                    "error": tables_result.get(
                        "error", "テーブル一覧の取得に失敗しました"
                    ),
                }

            tables = tables_result.get("tables", [])
            schema_info = {"tables": []}

            # 各テーブルのスキーマ情報を取得
            for table_name in tables:
                schema_result = await self.db_service.get_table_schema(table_name)
                if schema_result["success"]:
                    schema_info["tables"].append(
                        {
                            "name": table_name,
                            "columns": schema_result.get("columns", []),
                        }
                    )

            return {
                "success": True,
                "schema": schema_info,
            }
        except Exception as e:
            logger.error(f"Error getting database schema: {e}")
            return {
                "success": False,
                "error": f"データベーススキーマの取得中にエラーが発生しました: {str(e)}",
            }

    async def text_to_sql(
        self, text: str, schema_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        テキストからSQLクエリを生成する

        Args:
            text: 自然言語テキスト
            schema_info: データベーススキーマ情報（オプション）

        Returns:
            生成されたSQLクエリ情報
        """
        try:
            # スキーマ情報がない場合は取得
            if not schema_info:
                schema_result = await self.get_db_schema_info()
                if schema_result["success"]:
                    schema_info = schema_result.get("schema", {})
                else:
                    # スキーマ情報が取得できない場合でも処理を続行
                    schema_info = {"tables": []}

            # テーブル情報をフォーマット
            schema_text = "利用可能なテーブル:\n"
            for table in schema_info.get("tables", []):
                schema_text += f"- {table['name']}\n"
                schema_text += "  カラム:\n"
                for column in table.get("columns", []):
                    col_name = column.get("column_name", "")
                    data_type = column.get("data_type", "")
                    nullable = (
                        "NULL可" if column.get("is_nullable") == "YES" else "NOT NULL"
                    )
                    schema_text += f"    - {col_name} ({data_type}, {nullable})\n"

            # テキストからSQLクエリを生成するプロンプト
            generate_sql_prompt = PromptTemplate.from_template(
                """
                あなたは自然言語をSQLクエリに変換する専門家です。
                与えられたテキストを分析し、適切なSQLクエリを生成してください。

                # データベース情報
                {schema_text}

                # ユーザーの質問/要求
                {text}

                # 指示
                1. ユーザーの要求を分析し、必要なデータを取得するSQLクエリを生成してください。
                2. 利用可能なテーブルとカラム情報を考慮してください。
                3. クエリは標準的なSQL構文を使用し、見やすいフォーマットにしてください。
                4. JOINが必要な場合は適切に使用してください。
                5. 必要に応じてWHERE句、GROUP BY句、ORDER BY句などを使用してください。

                # 出力形式
                以下の形式でJSON出力してください:
                ```json
                {{
                  "query": "生成したSQLクエリ",
                  "explanation": "このクエリがユーザーの要求にどう対応しているかの説明",
                  "confidence": 0.0-1.0  // クエリの確信度（0.0〜1.0の数値）
                }}
                ```
                """
            )

            # クエリを生成
            generate_chain = generate_sql_prompt | self.llm | StrOutputParser()
            generate_result = await generate_chain.ainvoke(
                {"text": text, "schema_text": schema_text}
            )

            # JSONを抽出して解析
            json_match = re.search(r"```json\s*(.*?)\s*```", generate_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = generate_result

            generate_data = json.loads(json_str)
            sql_query = generate_data.get("query", "")
            explanation = generate_data.get("explanation", "")
            confidence = generate_data.get("confidence", 0.0)

            if not sql_query:
                return {
                    "success": False,
                    "error": "SQLクエリを生成できませんでした",
                    "query": "",
                    "explanation": "",
                }

            # クエリを分析して正当性をチェック
            analysis = await self.analyze_query(sql_query)

            # クエリが無効で修正が必要な場合
            if not analysis.get("is_valid", True) and analysis.get("corrected_query"):
                # 修正されたクエリを使用
                corrected_query = analysis.get("corrected_query", "")

                return {
                    "success": True,
                    "query_modified": True,
                    "original_query": sql_query,
                    "query": corrected_query,
                    "explanation": explanation,
                    "confidence": confidence,
                    "error_details": analysis.get("error_details", ""),
                }
            else:
                # 有効なクエリ
                return {
                    "success": True,
                    "query_modified": False,
                    "query": sql_query,
                    "explanation": explanation,
                    "confidence": confidence,
                }

        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            return {
                "success": False,
                "error": f"SQLクエリの生成中にエラーが発生しました: {str(e)}",
                "query": "",
                "explanation": "",
            }

    async def execute_db_query(self, task: MentionTask) -> Dict[str, Any]:
        """
        タスクからSQLクエリを抽出または生成し、実行する

        Args:
            task: メンションタスク

        Returns:
            クエリ実行結果
        """
        try:
            # データベーススキーマ情報を取得
            schema_result = await self.get_db_schema_info()
            schema_info = (
                schema_result.get("schema", {}) if schema_result["success"] else None
            )

            # テキストからSQLを生成
            sql_result = await self.text_to_sql(task.text, schema_info)

            if not sql_result["success"]:
                return {
                    "success": False,
                    "error": sql_result.get("error", "SQLクエリの生成に失敗しました"),
                    "query": "",
                    "results": [],
                }

            sql_query = sql_result["query"]
            explanation = sql_result.get("explanation", "")

            # クエリを実行
            db_result = await self.db_service.execute_query(sql_query)

            if db_result["success"]:
                return {
                    "success": True,
                    "query_modified": sql_result.get("query_modified", False),
                    "original_query": sql_result.get("original_query", ""),
                    "executed_query": sql_query,
                    "explanation": explanation,
                    "results": db_result.get("rows", [])
                    if "rows" in db_result
                    else [db_result.get("result", {})],
                }
            else:
                return {
                    "success": False,
                    "query_modified": sql_result.get("query_modified", False),
                    "original_query": sql_result.get("original_query", ""),
                    "executed_query": sql_query,
                    "explanation": explanation,
                    "error": db_result.get("error", "不明なエラー"),
                }

        except Exception as e:
            logger.error(f"Error executing database query: {e}")
            return {
                "success": False,
                "error": f"データベースクエリの実行中にエラーが発生しました: {str(e)}",
                "query": "",
                "results": [],
            }

    async def process(self, task: MentionTask) -> Dict[str, Any]:
        """
        タスクを処理する

        Args:
            task: 処理するタスク

        Returns:
            処理結果
        """
        try:
            # 入力テキストからデータベースクエリが必要かどうかを判断
            need_query_prompt = PromptTemplate.from_template(
                """
                あなたはメッセージを分析し、データベースクエリが必要かどうかを判断するAIアシスタントです。
                以下のメッセージを分析してください。

                # メッセージ
                {text}

                # 判断基準
                以下のような場合、データベースクエリが必要と判断してください：
                1. ユーザーがデータの検索や取得を明示的に要求している
                2. SQLクエリを含むか、データベース操作について言及している
                3. 特定の条件に基づくデータの抽出や集計を求めている

                # 出力形式
                データベースクエリが必要かどうかをTrue/Falseで出力してください：
                ```json
                {{
                  "needs_query": true|false,
                  "reason": "判断理由の簡潔な説明"
                }}
                ```
                """
            )

            need_query_chain = need_query_prompt | self.llm | StrOutputParser()
            need_query_result = await need_query_chain.ainvoke({"text": task.text})

            # JSONを抽出して解析
            json_match = re.search(
                r"```json\s*(.*?)\s*```", need_query_result, re.DOTALL
            )
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = need_query_result

            need_query_data = json.loads(json_str)
            needs_query = need_query_data.get("needs_query", False)

            if not needs_query:
                return {
                    "success": True,
                    "message": "データベースクエリは必要ありません",
                    "needs_query": False,
                    "reason": need_query_data.get("reason", ""),
                }

            # データベースクエリが必要な場合は実行
            query_result = await self.execute_db_query(task)

            # 結果のフォーマット
            return {
                "success": query_result.get("success", False),
                "needs_query": True,
                "query_result": query_result,
                "reason": need_query_data.get("reason", ""),
            }

        except Exception as e:
            logger.error(f"Error in database agent process: {e}")
            return {
                "success": False,
                "error": f"データベースエージェントの処理中にエラーが発生しました: {str(e)}",
            }
