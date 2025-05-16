import asyncio
import json
import logging
import os
from typing import Any, Dict

from core.slack_agent import SlackAgent
from core.workflow_manager import WorkflowManager
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from models.anthropic import AnthropicModelHandler

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def handle_slack_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Slackイベントを処理する関数

    Args:
        event_data: Slackから受信したイベントデータ

    Returns:
        処理結果
    """
    event_type = event_data.get("type")

    # app_mentionイベントの処理
    if event_type == "app_mention":
        text = event_data.get("text", "")
        channel = event_data.get("channel")
        thread_ts = event_data.get("thread_ts", event_data.get("ts"))

        # メンションテキストからボットIDを削除
        clean_text = text.split(">", 1)[-1].strip() if ">" in text else text

        # ワークフローマネージャーでリクエスト処理
        workflow_manager = WorkflowManager()
        return await workflow_manager.process_request(
            query=clean_text, channel_id=channel, thread_ts=thread_ts
        )

    return {"status": "unsupported_event"}


async def start_server():
    """Slackイベントを監視するサーバーを起動"""
    try:
        slack_agent = SlackAgent()

        # 初期化完了メッセージ
        logger.info("Slackボットサーバーが起動しました。イベントを待機しています...")

        # 実際のサーバー実装ではここでWebサーバーを起動し、
        # Slackからのイベントを受け取る処理を実装します

        # このサンプルではテスト実行用の処理
        test_event = {
            "type": "app_mention",
            "text": "<@BOTID> GitHubからmonorepo-exampleのリポジトリを検索して",
            "channel": "C123456",
            "ts": "1234567890.123456",
        }

        response = await handle_slack_event(test_event)
        logger.info(f"テスト実行結果: {response}")

    except Exception as e:
        logger.error(f"サーバー起動エラー: {str(e)}")


async def test_workflow():
    """ワークフローをテスト実行する関数"""
    workflow_manager = WorkflowManager()

    test_query = "GitHubからmonorepo-exampleのリポジトリを検索して、README.mdの内容を教えてください。"
    logger.info(f"テストクエリ: {test_query}")

    response = await workflow_manager.process_request(test_query)
    logger.info(f"テスト実行結果: {response}")


async def run_client() -> None:
    """MCPクライアントのテスト実行"""
    model_handler = AnthropicModelHandler()

    try:
        # GitHubのMCP設定を読み込み
        with open("mcp_config/github.json", "r") as f:
            mcp_config = json.load(f)

        async with MultiServerMCPClient(mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            agent = create_react_agent(model_handler.llm, tools)
            agent_response = await agent.ainvoke(
                {
                    "messages": "Githubからhttps://github.com/takeuchi-shogo/monorepo-example のリポジトリを取得して、このリポジトリのREADME.mdを取得してください。"
                }
            )

            print()
            print("応答:")
            print(agent_response)

    except FileNotFoundError:
        logger.error(
            "MCP設定ファイルが見つかりません。mcp_config/github.jsonを作成してください。"
        )
    except Exception as e:
        logger.error(f"エラー: {str(e)}")


if __name__ == "__main__":
    # コマンドライン引数などでモードを切り替える実装も可能
    mode = os.environ.get("RUN_MODE", "test_workflow")

    if mode == "server":
        asyncio.run(start_server())
    elif mode == "test_client":
        asyncio.run(run_client())
    else:
        asyncio.run(test_workflow())
