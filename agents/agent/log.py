import logging

from config.prompt import SENTRY_RESPONSE_SYSTEM_PROMPT
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

    async def execute(self, query: str, state: State) -> str:
        """
        ログを取得する
        取得したログをStateに格納する
        """
        # Sentryのツールを取得
        tools = await self.mcp_client.get_sentry_tools()
        logger.info(f"SentryAgent取得したツール数: {len(tools)}")
        for i, tool in enumerate(tools):
            logger.info(
                f"ツール{i}: {tool.name if hasattr(tool, 'name') else str(tool)}"
            )

        agent = create_react_agent(
            self.model_handler.llm,
            tools,
        )

        agent_response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": SENTRY_RESPONSE_SYSTEM_PROMPT},
                ],
            }
        )

        logger.info(f"SentryAgent raw response: {agent_response}")

        return agent_response
