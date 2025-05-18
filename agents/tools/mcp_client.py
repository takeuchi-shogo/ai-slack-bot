import asyncio
import json
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCPクライアントを管理するクラス
    """

    def __init__(self):
        self.github = asyncio.run(self.initialize_github())

    async def initialize_github(self):
        """
        GitHubのMCPクライアントを初期化する
        """
        with open("tools/schema/github.json", "r") as f:
            mcp_config = json.load(f)

        # コンテキストマネージャを使わない
        client = MultiServerMCPClient(mcp_config["mcpServers"])
        # 直接ツールを取得
        tools = await client.get_tools()
        return tools
