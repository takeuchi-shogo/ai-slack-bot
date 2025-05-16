import json
import logging
from typing import Any, Dict

from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class ControllerAgent:
    """エージェント間の連携とタスク分配を管理するエージェント"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.mcp_config = None

        try:
            with open("mcp_config/controller.json", "r") as f:
                self.mcp_config = json.load(f)
        except FileNotFoundError:
            logger.error("Controller MCP設定ファイルが見つかりません")
            raise

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """ユーザークエリを分析し最適なエージェントを決定する

        Args:
            query: ユーザーからのクエリ

        Returns:
            分析結果（ルーティング情報など）
        """
        # 分析用プロンプト
        prompt = f"""
        以下のユーザークエリを分析し、どのエージェントで処理すべきか判断してください：
        
        クエリ: {query}
        
        利用可能なエージェント:
        1. GitHub - コードリポジトリの検索や分析
        2. データベース - データベースへのクエリ
        3. Notion - タスク管理や情報整理
        4. Slack - メッセージの送信や返信
        
        以下の形式で応答してください：
        
        エージェント: [適切なエージェント名]
        アクション: [必要なアクション]
        理由: [選択した理由の簡潔な説明]
        パラメータ: [アクションに必要なパラメータ]
        """

        # 分析実行
        response = await self.model_handler.llm.ainvoke(
            [{"content": prompt, "role": "user"}]
        )
        analysis_text = response.content

        # テキスト応答を構造化データに変換
        return self._parse_analysis(analysis_text)

    def _parse_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """分析テキストから構造化データを抽出する

        Args:
            analysis_text: 分析テキスト

        Returns:
            構造化データ
        """
        lines = analysis_text.strip().split("\n")
        result = {
            "agent": "slack",  # デフォルト
            "action": "respond",
            "reason": "",
            "parameters": {},
        }

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "エージェント" or key == "agent":
                result["agent"] = value.lower()
            elif key == "アクション" or key == "action":
                result["action"] = value.lower()
            elif key == "理由" or key == "reason":
                result["reason"] = value
            elif key == "パラメータ" or key == "parameters":
                # パラメータの解析（実際の実装では詳細な解析が必要）
                try:
                    if "{" in value and "}" in value:
                        # JSONとして解析
                        param_str = value[value.find("{") : value.rfind("}") + 1]
                        result["parameters"] = json.loads(param_str)
                    else:
                        # キーバリューペアとして解析
                        params = {}
                        param_pairs = value.split(",")
                        for pair in param_pairs:
                            if "=" in pair:
                                p_key, p_value = pair.split("=", 1)
                                params[p_key.strip()] = p_value.strip()
                        result["parameters"] = params
                except Exception as e:
                    logger.error(f"パラメータ解析エラー: {str(e)}")

        return result

    async def get_controller(self, controller_name: str) -> Any:
        """名前指定でコントローラーインスタンスを取得する

        Args:
            controller_name: コントローラー名

        Returns:
            コントローラーインスタンス
        """
        if controller_name.lower() == "github":
            from agents.github import GithubAgent

            return GithubAgent()
        elif controller_name.lower() == "database":
            from agents.database import DatabaseAgent

            return DatabaseAgent()
        elif controller_name.lower() == "notion":
            from core.notion_agent import NotionAgent

            return NotionAgent()
        elif controller_name.lower() == "slack":
            from core.slack_agent import SlackAgent

            return SlackAgent()
        else:
            # デフォルトはSlack
            from core.slack_agent import SlackAgent

            return SlackAgent()

    async def route_query(self, query: str) -> Dict[str, Any]:
        """クエリを分析し適切なエージェントにルーティングする

        Args:
            query: ユーザークエリ

        Returns:
            処理結果
        """
        # クエリ分析
        analysis = await self.analyze_query(query)
        logger.info(f"クエリ分析結果: {analysis}")

        # 適切なエージェントを取得
        agent = await self.get_controller(analysis["agent"])

        # エージェントにクエリを処理させる
        if analysis["agent"] == "github":
            if hasattr(agent, analysis["action"]):
                method = getattr(agent, analysis["action"])
                return await method(**analysis["parameters"])
            else:
                # デフォルトはsimple_chat
                return await agent.simple_chat(query)

        elif analysis["agent"] == "database":
            # DatabaseAgentの場合
            return await agent.process_query(query)

        elif analysis["agent"] == "notion":
            # NotionAgentの場合
            if analysis["action"] == "create_task":
                task_info = await agent.format_task_from_query(query)
                return await agent.create_task(**task_info)
            else:
                # 他のNotionアクション
                return {"response": "この操作はまだサポートされていません"}

        else:
            # デフォルトはSlackのprocess_mention
            return await agent.process_mention(query)
