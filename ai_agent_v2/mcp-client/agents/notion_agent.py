"""
Notionタスク作成エージェントモジュール

GitHubリサーチ結果に基づいてNotionにタスクを作成するエージェントを提供します
LangGraphフレームワークに対応
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config import get_agent_prompts
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tools.handlers import ToolManager

logger = logging.getLogger(__name__)


class NotionTaskAgent:
    """
    Notionタスク作成エージェント

    GitHubリサーチ結果を分析し、適切なタスクをNotion上に作成します。
    LangGraphのエージェントノードとして機能します。
    """

    def __init__(
        self,
        llm: Optional[ChatAnthropic] = None,
        tool_manager: Optional[ToolManager] = None,
    ):
        """
        NotionTaskAgentの初期化

        Args:
            llm: 言語モデル
            tool_manager: MCPツール管理のインスタンス
        """
        self.llm = llm
        self.tool_manager = tool_manager
        self.prompts = get_agent_prompts()

    async def _find_database_id(self) -> Optional[str]:
        """
        適切なNotionデータベースIDを検索

        Returns:
            Optional[str]: 見つかったデータベースID、見つからない場合はNone
        """
        try:
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            if "notion_list_databases" not in tool_names:
                logger.warning("notion_list_databasesツールが利用できません")
                return None

            databases_info = await self.tool_manager.execute_tool(
                "notion_list_databases", {}
            )

            try:
                if isinstance(
                    databases_info, str
                ) and databases_info.strip().startswith("{"):
                    databases = json.loads(databases_info)

                    for db in databases.get("results", []):
                        db_title = db.get("title", "").lower()
                        if any(
                            keyword in db_title
                            for keyword in [
                                "task",
                                "タスク",
                                "project",
                                "プロジェクト",
                                "todo",
                                "タスク",
                            ]
                        ):
                            return db.get("id")
            except (json.JSONDecodeError, AttributeError) as e:
                logger.error(f"データベース情報のパースエラー: {str(e)}")

            return None
        except Exception as e:
            logger.error(f"データベースID検索エラー: {str(e)}")
            return None

    async def _generate_task_content(
        self, github_result: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """
        タスク内容を生成

        Args:
            github_result: GitHubリサーチ結果
            query: 元のユーザークエリ

        Returns:
            Dict[str, Any]: タスク作成のための情報
        """
        # GitHubの情報を抽出
        code_analyses = github_result.get("code_analyses", [])
        summary = github_result.get("summary", "")
        raw_info = github_result.get("raw_info", [])

        # タスクタイトルの取得
        task_title = "コード修正タスク"
        file_paths = []

        for analysis in code_analyses:
            file_path = analysis.get("file")
            if file_path:
                file_paths.append(file_path)

        if file_paths:
            task_title = f"{file_paths[0]} の修正"

        # 問題点の抽出
        issue_summary = []
        for analysis in code_analyses:
            analysis_text = analysis.get("analysis", "")
            # 箇条書きを抽出
            issue_lines = [
                line.strip()
                for line in analysis_text.split("\n")
                if line.strip().startswith("-")
            ]
            issue_summary.extend([line[2:].strip() for line in issue_lines])

        # LLMを使用してタスク内容を生成
        notion_prompt = self.prompts.get("notion_task", "")
        combined_info = "\n\n".join(raw_info[:3]) if raw_info else summary

        messages = [
            SystemMessage(content=notion_prompt),
            HumanMessage(
                content=f"GitHubリサーチ結果に基づいて、Notionに作成するタスクの内容を生成してください。\n\nユーザークエリ: {query}\n\n"
                f"対象ファイル: {', '.join(file_paths) if file_paths else '未特定'}\n\n"
                f"検出された問題点:\n{'- ' + '\n- '.join(issue_summary) if issue_summary else '詳細な問題点は検出されませんでした'}\n\n"
                f"GitHub分析結果:\n{summary}\n\n"
                f"タスクの説明文（修正手順を含む）を作成してください。タスクの優先度（高/中/低）も推奨してください。"
            ),
        ]

        response = await self.llm.ainvoke(messages)
        task_description = response.content

        # 優先度を抽出（デフォルトは中）
        priority = "中"
        priority_match = re.search(
            r"優先度[：:]\s*([高中低]|high|medium|low)", task_description, re.IGNORECASE
        )
        if priority_match:
            extracted_priority = priority_match.group(1).lower()
            if extracted_priority in ["高", "high"]:
                priority = "高"
            elif extracted_priority in ["低", "low"]:
                priority = "低"

        # 期限の設定（1週間後）
        due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        return {
            "title": task_title,
            "description": task_description,
            "priority": priority,
            "due_date": due_date,
            "file_paths": file_paths,
            "issues": issue_summary,
        }

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        状態を処理してNotionタスクを作成

        LangGraphのノード関数として機能し、状態を更新します。

        Args:
            state: 現在の状態

        Returns:
            Dict[str, Any]: 更新された状態
        """
        query = state.get("query", "")
        github_result = state.get("github_result", {})

        try:
            if not self.tool_manager:
                raise ValueError("ToolManagerが初期化されていません")

            if not github_result:
                logger.warning("GitHubリサーチ結果がありません")
                return {
                    "notion_result": {
                        "error": "GitHubリサーチ結果がないため、タスクを作成できません"
                    },
                    "response": "GitHubリサーチ結果がないため、Notionタスクを作成できませんでした。",
                }

            # ツールの利用可能性を確認
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            if "notion_create_page" not in tool_names:
                logger.warning("notion_create_pageツールが利用できません")
                return {
                    "notion_result": {
                        "error": "Notionページ作成ツールが利用できません"
                    },
                    "response": "Notionページ作成ツールが利用できないため、タスクを作成できませんでした。",
                }

            # データベースIDを検索
            database_id = await self._find_database_id()
            if not database_id:
                logger.warning("タスク用のNotionデータベースが見つかりません")
                return {
                    "notion_result": {
                        "error": "タスク用のNotionデータベースが見つかりません"
                    },
                    "response": "タスク用のNotionデータベースが見つからないため、タスクを作成できませんでした。",
                }

            # タスク内容を生成
            task_content = await self._generate_task_content(github_result, query)

            # Notionのプロパティを設定
            properties = {
                "Name": {"title": [{"text": {"content": task_content.get("title")}}]},
                "Status": {"select": {"name": "未着手"}},
                "Priority": {"select": {"name": task_content.get("priority", "中")}},
            }

            # 期限を追加
            properties["Due"] = {"date": {"start": task_content.get("due_date")}}

            # タスク説明を整形
            description = f"""
## 修正タスク

### 元のクエリ
{query}

### 対象ファイル
{", ".join(task_content.get("file_paths", [])) if task_content.get("file_paths") else "特定のファイルは指定されていません"}

### 検出された問題点
{"- " + "\n- ".join(task_content.get("issues", [])) if task_content.get("issues") else "詳細な問題点は検出されませんでした"}

### 詳細説明
{task_content.get("description", "")}

### GitHub分析情報
```
{github_result.get("summary", "")[:500]}{"..." if len(github_result.get("summary", "")) > 500 else ""}
```
            """

            # Notionにタスクを作成
            result = await self.tool_manager.execute_tool(
                "notion_create_page",
                {
                    "database_id": database_id,
                    "properties": properties,
                    "content": description,
                },
            )

            # ページURLを抽出
            page_url = None
            try:
                response_data = (
                    json.loads(result) if isinstance(result, str) else result
                )
                page_url = response_data.get("url")
            except (json.JSONDecodeError, AttributeError):
                page_url = "URL取得できませんでした"

            # 結果をフォーマット
            notion_result = {
                "task_title": task_content.get("title"),
                "database_id": database_id,
                "page_url": page_url,
                "properties": properties,
                "content": description,
            }

            # 応答メッセージを作成
            response = f"Notionタスク「{task_content.get('title')}」が作成されました。\nURL: {page_url}"

            # 状態を更新
            return {"notion_result": notion_result, "response": response}

        except Exception as e:
            logger.error(f"Notionタスクエージェント処理エラー: {str(e)}")

            # エラー時の状態更新
            return {
                "notion_result": {"error": str(e)},
                "response": f"Notionタスクの作成中にエラーが発生しました: {str(e)}",
            }
