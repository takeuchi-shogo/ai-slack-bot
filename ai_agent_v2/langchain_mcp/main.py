import asyncio
import json

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

load_dotenv()


async def run_client() -> None:
    model = ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        temperature=0,
    )

    with open("mcp_config.json", "r") as f:
        mcp_config = json.load(f)

    async with MultiServerMCPClient(mcp_config["mcpServers"]) as client:
        tools = client.get_tools()

        agent = create_react_agent(model, tools)
        agent_response = await agent.ainvoke(
            {
                "messages": "Githubからhttps://github.com/takeuchi-shogo/monorepo-example のリポジトリを取得して、このリポジトリのREADME.mdを取得してください。"
            }
        )

        print()
        print("response:")
        print(agent_response)


if __name__ == "__main__":
    asyncio.run(run_client())
