import logging

from agent.state import State
from config.prompt import GITHUB_RESEARCH_SYSTEM_PROMPT
from langgraph.prebuilt import create_react_agent
from models.gemini import GeminiModelHandler
from tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class CodeReviewAgent:
    """
    コードレビューを行うエージェント

    GitHubからコードを取得し、コードレビューを行う
    """

    def __init__(self):
        self.model_handler = GeminiModelHandler()
        self.mcp_client = MCPClient()

    async def execute(self, state: State) -> State:
        """
        Stateに格納されているDB情報、ログ情報を元に該当する怪しい箇所のコードをレビューする
        レビュー結果はStateに格納する
        """
        github_tools = self.mcp_client.get_github_tools()
        agent = create_react_agent(self.model_handler.llm, github_tools, verbose=True)

        # Stateから必要な情報を抽出してプロンプトを構築
        db_info = state.db_info if hasattr(state, "db_info") else ""
        log_info = state.log_info if hasattr(state, "log_info") else ""

        review_prompt = f"""
        以下の情報に基づいてコードをレビューしてください：
        
        データベース情報:
        {db_info}
        
        ログ情報:
        {log_info}
        """
        agent_response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": GITHUB_RESEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": review_prompt},
                ],
            }
        )
        return agent_response
