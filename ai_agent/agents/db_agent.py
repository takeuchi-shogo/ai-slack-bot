import json
import logging
import re
from typing import Any, Dict

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

    async def execute_db_query(self, task: MentionTask) -> Dict[str, Any]:
        """
        タスクからSQLクエリを抽出し、実行する

        Args:
            task: メンションタスク

        Returns:
            クエリ実行結果
        """
        try:
            # SQLクエリを抽出するプロンプト
            extract_prompt = PromptTemplate.from_template(
                """
                あなたはメッセージからSQLクエリを抽出するAIアシスタントです。
                以下のメッセージを分析し、含まれているSQLクエリを抽出してください。

                # メッセージ
                {text}

                # 指示
                1. メッセージに含まれるSQLクエリを特定してください。
                2. SQLクエリが見つからない場合は、ユーザーが実行したいと思われるクエリを推測してください。
                3. SQLクエリを整形して出力してください。

                # 出力形式
                以下の形式でJSON出力してください:
                ```json
                {{
                  "query": "抽出または推測したSQLクエリ",
                  "is_extracted": true|false  // クエリが直接抽出されたか推測されたか
                }}
                ```
                """
            )

            # クエリを抽出
            extract_chain = extract_prompt | self.llm | StrOutputParser()
            extract_result = await extract_chain.ainvoke({"text": task.text})

            # JSONを抽出して解析
            json_match = re.search(r"```json\s*(.*?)\s*```", extract_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = extract_result

            extract_data = json.loads(json_str)
            sql_query = extract_data.get("query", "")
            is_extracted = extract_data.get("is_extracted", False)

            if not sql_query:
                return {
                    "success": False,
                    "error": "SQLクエリを抽出できませんでした",
                    "query": "",
                    "results": [],
                }

            # クエリを分析して正当性をチェック
            analysis = await self.analyze_query(sql_query)

            # クエリが無効で修正が必要な場合
            if not analysis.get("is_valid", True) and analysis.get("corrected_query"):
                # 修正されたクエリを使用
                corrected_query = analysis.get("corrected_query", "")

                # 修正されたクエリを使ってデータベース検索を実行する
                db_result = await self.db_service.execute_query(corrected_query)

                if db_result["success"]:
                    return {
                        "success": True,
                        "query_modified": True,
                        "original_query": sql_query,
                        "executed_query": corrected_query,
                        "error_details": analysis.get("error_details", ""),
                        "results": db_result.get("rows", [])
                        if "rows" in db_result
                        else [db_result.get("result", {})],
                    }
                else:
                    # 修正したクエリも失敗した場合、エラー情報を返す
                    return {
                        "success": False,
                        "query_modified": True,
                        "original_query": sql_query,
                        "executed_query": corrected_query,
                        "error_details": analysis.get("error_details", ""),
                        "db_error": db_result.get("error", "不明なエラー"),
                    }
            else:
                # 正しいクエリを使ってデータベース検索を実行する
                # 実際にデータベースに接続して実行
                db_result = await self.db_service.execute_query(sql_query)

                if db_result["success"]:
                    return {
                        "success": True,
                        "query_modified": False,
                        "executed_query": sql_query,
                        "results": db_result.get("rows", [])
                        if "rows" in db_result
                        else [db_result.get("result", {})],
                    }
                else:
                    return {
                        "success": False,
                        "query_modified": False,
                        "executed_query": sql_query,
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
