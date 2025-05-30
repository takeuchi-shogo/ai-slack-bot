import logging
from typing import Any, Dict

from config.prompt import LOG_RESPONSE_SYSTEM_PROMPT
from langgraph.prebuilt import create_react_agent
from models.open_ai import OpenAIModelHandler
from tools.mcp_client import MCPClient

from agent.state import State

logger = logging.getLogger(__name__)


class LogAgent:
    """
    ログを取得するエージェント

    DataDogからログを取得する
    """

    def __init__(self):
        self.model_handler = OpenAIModelHandler()
        self.mcp_client = MCPClient()

    async def execute(self, query: str, state: State) -> Dict[str, Any]:
        """
        ログを取得する
        取得したログをStateに格納する
        """
        # Sentryのツールを取得
        tools = await self.mcp_client.get_sentry_tools()
        # Datadogのツールを取得
        tools = await self.mcp_client.get_datadog_tools()
        logger.info(f"Sentry, Datadog取得したツール数: {len(tools)}")
        for i, tool in enumerate(tools):
            logger.info(
                f"ツール{i}: {tool.name if hasattr(tool, 'name') else str(tool)}"
            )

        agent = create_react_agent(
            self.model_handler.llm,
            tools,
            prompt=LOG_RESPONSE_SYSTEM_PROMPT,
        )

        agent_response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": LOG_RESPONSE_SYSTEM_PROMPT},
                    {"role": "user", "content": await self.generate_log_query(state)},
                ],
            }
        )

        logger.info(f"LogAgent raw response: {agent_response}")

        return agent_response

    async def generate_log_query(self, state: State) -> str:
        """
        ログを取得するためのクエリを生成する
        """
        angent_result_messages = ""
        for message in state.messages:
            angent_result_messages += f"{message.agent_name}: {message.message}\n"

        query = f"""
        ユーザーのリクエスト: {state.query}
        これまでのエージェントの応答: {angent_result_messages}
        ログを取得するためのクエリを生成してください。
        """
        return query
