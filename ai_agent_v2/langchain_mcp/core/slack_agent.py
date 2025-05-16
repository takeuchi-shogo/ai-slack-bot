import json
import logging
from typing import Any, Dict

from config import SLACK_RESPONSE_SYSTEM_PROMPT
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class SlackAgent:
    """Slackとのインタラクションを処理するエージェント"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.mcp_config = None

        try:
            with open("mcp_config/slack.json", "r") as f:
                self.mcp_config = json.load(f)
        except FileNotFoundError:
            logger.error("Slack MCP設定ファイルが見つかりません")
            raise

    async def process_mention(
        self, message: str, channel_id: str = None, thread_ts: str = None
    ) -> Dict[str, Any]:
        """Slackメンションを処理し適切な応答を返す

        Args:
            message: ユーザーからのメッセージ
            channel_id: メッセージが送信されたチャンネルID
            thread_ts: メッセージのスレッドタイムスタンプ

        Returns:
            Slackに送信する応答
        """
        # Slackの応答用MCPクライアント
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            # ReActエージェントの作成
            agent = create_react_agent(
                self.model_handler.llm,
                tools,
                system_message=SLACK_RESPONSE_SYSTEM_PROMPT,
            )

            # エージェントに問い合わせ
            agent_response = await agent.ainvoke(
                {
                    "messages": message,
                    "context": {"channel_id": channel_id, "thread_ts": thread_ts},
                }
            )

            return agent_response

    async def send_response(
        self, channel_id: str, text: str, thread_ts: str = None
    ) -> Dict[str, Any]:
        """Slackチャンネルにメッセージを送信する

        Args:
            channel_id: 送信先チャンネルID
            text: 送信するテキスト
            thread_ts: スレッドのタイムスタンプ（スレッド返信の場合）

        Returns:
            Slack APIのレスポンス
        """
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            slack_tools = [
                tool for tool in client.get_tools() if tool.name.startswith("slack")
            ]

            # 適切なSlack送信ツールを探す
            send_message_tool = next(
                (tool for tool in slack_tools if "postMessage" in tool.name), None
            )

            if not send_message_tool:
                logger.error("Slack送信ツールが見つかりません")
                return {"error": "Slack送信ツールが見つかりません"}

            # メッセージ送信パラメータ
            params = {"channel": channel_id, "text": text}

            if thread_ts:
                params["thread_ts"] = thread_ts

            # ツールを使ってメッセージを送信
            response = await client.ainvoke_tool(send_message_tool, params)
            return response
