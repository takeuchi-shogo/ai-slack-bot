import json

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

load_dotenv()


class GithubAgent:
    def __init__(self):
        self.model = ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            temperature=0,
        )
        self.mcp_config = None

        with open("mcp_config/github.json", "r") as f:
            self.mcp_config = json.load(f)

    async def simple_chat(self, message: str):
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            agent = create_react_agent(self.model, tools)
            agent_response = await agent.ainvoke(
                {
                    "messages": message,
                }
            )

            return agent_response
