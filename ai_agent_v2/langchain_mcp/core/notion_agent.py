import json
import logging
from typing import Any, Dict, List

from config import NOTION_TASK_SYSTEM_PROMPT
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class NotionAgent:
    """Notionとの連携を処理するエージェント"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.mcp_config = None

        try:
            with open("mcp_config/notion.json", "r") as f:
                self.mcp_config = json.load(f)
        except FileNotFoundError:
            logger.error("Notion MCP設定ファイルが見つかりません")
            raise

    async def create_task(
        self, title: str, description: str, tags: List[str] = None
    ) -> Dict[str, Any]:
        """Notionにタスクを作成する

        Args:
            title: タスクのタイトル
            description: タスクの詳細説明
            tags: タスクに付けるタグのリスト

        Returns:
            作成されたタスクの情報
        """
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            # NotionのCreatePage APIに対応するツールを探す
            create_page_tool = next(
                (
                    tool
                    for tool in tools
                    if "notion" in tool.name.lower() and "page" in tool.name.lower()
                ),
                None,
            )

            if not create_page_tool:
                logger.error("Notion タスク作成ツールが見つかりません")
                return {"error": "Notion タスク作成ツールが見つかりません"}

            # タスク作成パラメータ
            params = {
                "parent": {"database_id": self.mcp_config.get("taskDatabaseId", "")},
                "properties": {
                    "Name": {"title": [{"text": {"content": title}}]},
                    "Status": {"select": {"name": "Not started"}},
                },
            }

            # タグの追加（設定がある場合）
            if tags and len(tags) > 0:
                params["properties"]["Tags"] = {
                    "multi_select": [{"name": tag} for tag in tags]
                }

            # 説明の追加
            params["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": description}}]},
                }
            ]

            # ツールを使ってタスクを作成
            response = await client.ainvoke_tool(create_page_tool, params)
            return response

    async def format_task_from_query(
        self, query: str, thread_url: str = None
    ) -> Dict[str, Any]:
        """ユーザークエリを分析し、適切なNotionタスクのフォーマットに変換する

        Args:
            query: ユーザーからのクエリ文字列
            thread_url: 関連するSlackスレッドのURL

        Returns:
            タスクのフォーマット（タイトル、説明、タグ）
        """
        # エージェントのプロンプト作成
        prompt = f"""
        以下のユーザークエリを分析し、Notionタスクを作成するためのフォーマット情報を提供してください。
        
        クエリ: {query}
        
        タスクに関連するSlackスレッドURL: {thread_url or "なし"}
        
        1. タスクのタイトル
        2. タスクの詳細説明（修正が必要な理由、修正手順を含む）
        3. タスクに付けるべきタグ（システム、バグ修正、機能追加など）
        
        これらの情報をJSON形式で提供してください。
        """

        # ReActエージェントを作成
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            agent = create_react_agent(
                self.model_handler.llm, tools, system_message=NOTION_TASK_SYSTEM_PROMPT
            )

            # エージェントに問い合わせ
            agent_response = await agent.ainvoke({"messages": prompt})

            # 応答からタスク情報を抽出
            try:
                task_info = json.loads(agent_response.get("response", "{}"))
                return {
                    "title": task_info.get("title", "未タイトル"),
                    "description": task_info.get("description", ""),
                    "tags": task_info.get("tags", []),
                }
            except json.JSONDecodeError:
                logger.error("タスク情報のJSON解析に失敗しました")
                return {
                    "title": "未分類のタスク",
                    "description": f"クエリ: {query}\nスレッド: {thread_url or 'なし'}",
                    "tags": ["要分類"],
                }
