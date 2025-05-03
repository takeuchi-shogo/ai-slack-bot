"""
Notion サービスモジュール

Notion APIとの連携機能を提供します
"""

import json
import re
from datetime import datetime, timedelta


class NotionService:
    """
    Notionサービスを管理するクラス
    """

    def __init__(self, tool_manager):
        """
        NotionServiceの初期化

        Args:
            tool_manager: ツール管理インスタンス
        """
        self.tool_manager = tool_manager

    async def create_notion_task(self, github_info: str, original_query: str) -> str:
        """
        Notionにタスクを作成

        Args:
            github_info: GitHubから取得した情報
            original_query: 元のユーザークエリ

        Returns:
            str: タスク作成結果のメッセージ
        """
        try:
            # Check available Notion tools
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            if "notion_create_page" not in tool_names:
                return "Notionページ作成ツールが利用できません"

            # Extract key information from GitHub info to create a meaningful task
            # Look for code issues or problems mentioned in the GitHub info
            task_title = "コード修正タスク"
            issue_summary = []
            code_file = None

            # Extract file paths mentioned
            file_paths = re.findall(r"ファイル「([^」]+)」", github_info)
            if file_paths:
                code_file = file_paths[0]
                task_title = f"{code_file} の修正"

            # Extract issues
            issues_section = None
            if "問題分析" in github_info:
                analysis_parts = github_info.split("問題分析:")
                if len(analysis_parts) > 1:
                    issues_section = analysis_parts[1].strip()

            if issues_section:
                # Extract bullet points
                issue_lines = [
                    line.strip()
                    for line in issues_section.split("\n")
                    if line.strip().startswith("-")
                ]
                issue_summary = [line[2:].strip() for line in issue_lines]

            # Create task description
            task_description = f"""
## 修正タスク

### 元のクエリ
{original_query}

### 対象ファイル
{code_file if code_file else "特定のファイルは指定されていません"}

### 検出された問題点
{"- " + "\n- ".join(issue_summary) if issue_summary else "詳細な問題点は検出されませんでした"}

### GitHub情報
```
{github_info[:500]}{"..." if len(github_info) > 500 else ""}
```

### 修正手順
1. 該当コードを確認する
2. 問題点を理解する
3. 修正案を検討する
4. 修正を実装する
5. テストを実施する
6. プルリクエストを作成する
            """

            # Look for appropriate Notion database ID
            # First try to see if we can list databases
            database_id = None
            if "notion_list_databases" in tool_names:
                result = await self.tool_manager.execute_tool(
                    "notion_list_databases", {}
                )
                databases_info = result

                # Try to find a Tasks or Projects database
                try:
                    if isinstance(
                        databases_info, str
                    ) and databases_info.strip().startswith("{"):
                        databases = json.loads(databases_info)
                        for db in databases.get("results", []):
                            db_title = db.get("title", "").lower()
                            if (
                                "task" in db_title
                                or "project" in db_title
                                or "todo" in db_title
                            ):
                                database_id = db.get("id")
                                break
                except (json.JSONDecodeError, AttributeError):
                    pass

            # If we couldn't find a database ID, use a default task database ID if available
            if not database_id:
                # Default database ID might be set in the future or obtained from environment
                # For now, we'll return an error if we can't find one
                return "タスク用のNotionデータベースが見つかりませんでした"

            # Create the task in Notion
            properties = {
                "Name": {"title": [{"text": {"content": task_title}}]},
                "Status": {"select": {"name": "未着手"}},
                "Priority": {"select": {"name": "中"}},
            }

            # Add a due date about a week from now
            due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            properties["Due"] = {"date": {"start": due_date}}

            # Create the page
            result = await self.tool_manager.execute_tool(
                "notion_create_page",
                {
                    "database_id": database_id,
                    "properties": properties,
                    "content": task_description,
                },
            )

            response_content = result

            # Extract page URL for easy access
            page_url = None
            try:
                response_data = (
                    json.loads(response_content)
                    if isinstance(response_content, str)
                    else response_content
                )
                page_url = response_data.get("url")
            except (json.JSONDecodeError, AttributeError):
                page_url = "URL取得できませんでした"

            return f"Notionタスク「{task_title}」が作成されました。\nURL: {page_url}"

        except Exception as e:
            return f"Notionタスク作成エラー: {str(e)}"
