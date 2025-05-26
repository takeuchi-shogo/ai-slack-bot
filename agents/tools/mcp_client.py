import json
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCPクライアントを管理するクラス
    """

    def __init__(self):
        self.github = None
        self.slack = None
        self._initialized = False

    async def _ensure_initialized(self):
        """遅延初期化でMCPクライアントをセットアップ"""
        if not self._initialized:
            try:
                self.github = await self.initialize_github()
                self.slack = await self.initialize_slack()
                self._initialized = True
                logger.info("MCPClient初期化完了")
            except Exception as e:
                logger.error(f"MCPClient初期化エラー: {type(e).__name__}: {str(e)}")
                # エラー時はダミーツールリストを返す
                self.github = []
                self.slack = []
                self._initialized = True

    async def get_github_tools(self):
        """GitHubツールを取得"""
        await self._ensure_initialized()
        return self.github

    async def get_slack_tools(self):
        """Slackツールを取得"""
        await self._ensure_initialized()
        return self.slack

    async def initialize_github(self):
        """
        GitHubのMCPクライアントを初期化する
        """
        try:
            with open("tools/schema/github.json", "r") as f:
                mcp_config = json.load(f)

            # コンテキストマネージャを使わない
            client = MultiServerMCPClient(mcp_config["mcpServers"])
            # 直接ツールを取得
            tools = await client.get_tools()
            return tools
        except Exception as e:
            logger.error(f"GitHub MCP初期化エラー: {e}")
            return []

    async def initialize_slack(self):
        """
        SlackのMCPクライアントを初期化する
        """
        try:
            with open("tools/schema/slack.json", "r") as f:
                mcp_config = json.load(f)

            # コンテキストマネージャを使わない
            client = MultiServerMCPClient(mcp_config["mcpServers"])
            # 直接ツールを取得
            tools = await client.get_tools()
            return tools
        except Exception as e:
            logger.error(f"Slack MCP初期化エラー: {e}")
            return []
