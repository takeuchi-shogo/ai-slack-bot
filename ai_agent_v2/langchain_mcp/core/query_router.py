import json
import logging
from typing import Any, Dict

from config import CONTROLLER_SYSTEM_PROMPT
from langchain_core.messages import HumanMessage, SystemMessage
from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class QueryRouter:
    """ユーザークエリを分析し適切なエージェントにルーティングするクラス"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.controller_config = None

        try:
            with open("mcp_config/controller.json", "r") as f:
                self.controller_config = json.load(f)
        except FileNotFoundError:
            logger.error("Controller MCP設定ファイルが見つかりません")
            raise

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """ユーザークエリを分析し、必要なエージェントと操作を決定する

        Args:
            query: ユーザーからのクエリ文字列

        Returns:
            分析結果（エージェントタイプ、アクション、パラメータなど）
        """
        messages = [
            SystemMessage(content=CONTROLLER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"以下のユーザーからのクエリを分析し、必要なエージェントとアクションを判断してください: {query}"
            ),
        ]

        response = await self.model_handler.llm.ainvoke(messages)

        # 応答を構造化データに変換
        try:
            analysis = self._parse_analysis(response.content)
            return analysis
        except Exception as e:
            logger.error(f"クエリ分析の解析エラー: {str(e)}")
            return {
                "agent_type": "default",
                "action": "respond",
                "parameters": {"query": query},
            }

    def _parse_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """LLMからの応答を構造化データに変換する

        分析テキストから以下の情報を抽出:
        - agent_type: 'github', 'database', 'notion', 'slack'
        - action: 実行するアクション
        - parameters: アクションに必要なパラメータ
        """
        # 基本的な応答構造
        result = {"agent_type": "default", "action": "respond", "parameters": {}}

        # テキスト内容から情報を抽出
        # 実際の実装ではもっと堅牢な解析が必要
        if "github" in analysis_text.lower():
            result["agent_type"] = "github"
        elif (
            "データベース" in analysis_text.lower()
            or "database" in analysis_text.lower()
        ):
            result["agent_type"] = "database"
        elif "notion" in analysis_text.lower() or "タスク" in analysis_text.lower():
            result["agent_type"] = "notion"

        # アクションの特定
        if "検索" in analysis_text.lower() or "search" in analysis_text.lower():
            result["action"] = "search"
        elif "作成" in analysis_text.lower() or "create" in analysis_text.lower():
            result["action"] = "create"
        elif "更新" in analysis_text.lower() or "update" in analysis_text.lower():
            result["action"] = "update"

        return result

    async def route_to_agent(
        self, analysis: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """分析結果に基づいて適切なエージェントにクエリをルーティングする

        Args:
            analysis: クエリ分析結果
            query: 元のユーザークエリ

        Returns:
            エージェントからの応答
        """
        agent_type = analysis.get("agent_type", "default")
        action = analysis.get("action", "respond")
        parameters = analysis.get("parameters", {})

        if agent_type == "github":
            from agents.github import GithubAgent

            github_agent = GithubAgent()
            return await github_agent.simple_chat(query)

        elif agent_type == "database":
            # データベースエージェント処理の実装
            # return await database_agent.process_query(query)
            return {"response": "データベースクエリの処理はまだ実装されていません"}

        elif agent_type == "notion":
            # Notionエージェント処理の実装
            # Notionクライアントを使用してタスク作成など
            return {"response": "Notionへのタスク作成はまだ実装されていません"}

        else:
            # デフォルトの応答
            from core.slack_agent import SlackAgent

            slack_agent = SlackAgent()
            return await slack_agent.process_mention(query)
