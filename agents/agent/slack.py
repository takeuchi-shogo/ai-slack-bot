import logging
from typing import List

from config.prompt import SLACK_RESPONSE_SYSTEM_PROMPT
from langgraph.prebuilt import create_react_agent
from models.open_ai import OpenAIModelHandler
from tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class SlackAgent:
    def __init__(self):
        self.mcp_client = MCPClient()
        self.model_handler = OpenAIModelHandler()

    async def send_message(self, channel_ids: List[str], message: str, thread_ts: str):
        try:
            tools = await self.mcp_client.get_slack_tools()
            logger.info(f"SlackAgent取得したツール数: {len(tools)}")
            for i, tool in enumerate(tools):
                logger.info(
                    f"ツール{i}: {tool.name if hasattr(tool, 'name') else str(tool)}"
                )

            agent = create_react_agent(
                self.model_handler.llm,
                tools,
            )

            # Slackに実際に送信するようにプロンプトを明確化
            enhanced_message = f"""
ユーザーからのメッセージ: {message}
チャンネルID: {channel_ids}
スレッドタイムスタンプ: {thread_ts}

あなたは必ずSlackツール（slack関連のツール）を使用して、上記のメッセージに対する適切な返答を指定されたSlackチャンネルに送信してください。
LLMでの応答生成だけではなく、実際にSlackのpostMessage機能を使用してメッセージを投稿することが重要です。
"""

            agent_response = await agent.ainvoke(
                {
                    "messages": [
                        {"role": "system", "content": SLACK_RESPONSE_SYSTEM_PROMPT},
                        {"role": "user", "content": enhanced_message},
                    ],
                    "context": {"channel_ids": channel_ids, "thread_ts": thread_ts},
                }
            )
            logger.info(f"SlackAgent raw response: {agent_response}")

            # agent_responseの形式を確認して適切にcontentを抽出
            if hasattr(agent_response, "content"):
                content = agent_response.content
            elif isinstance(agent_response, dict) and "content" in agent_response:
                content = agent_response["content"]
            elif isinstance(agent_response, dict) and "messages" in agent_response:
                # messages配列から最後のメッセージを取得
                last_message = agent_response["messages"][-1]
                if hasattr(last_message, "content"):
                    content = last_message.content
                else:
                    content = str(last_message)
            else:
                content = str(agent_response)

            return {"content": content}

        except Exception as e:
            logger.error(f"SlackAgent.send_message error: {type(e).__name__}: {str(e)}")
            import traceback

            logger.error(f"SlackAgent traceback: {traceback.format_exc()}")
            return {"content": f"Slack送信処理でエラーが発生しました: {str(e)}"}
