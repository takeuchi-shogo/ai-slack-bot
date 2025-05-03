"""
ベースクラスモジュール

MCPクライアントの基本クラスと共通機能を提供します
"""

from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters, stdio_client


class BaseMCPClient:
    """
    MCPクライアントの基本クラス

    基本的なセッション管理、サーバー接続、クリーンアップ機能を提供します。
    """

    def __init__(self):
        """
        BaseMCPClientの初期化
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.stdio = None
        self.write = None
        self.current_server = None
        self.default_channel_id = None

    async def connect_to_server(
        self, server_params: StdioServerParameters, server_name: str
    ):
        """
        MCPサーバーに接続

        Args:
            server_params: サーバー接続パラメータ
            server_name: 接続するサーバーの名前
        """
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()
        self.current_server = server_name

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(
            f"\nConnected to {self.current_server} server with tools:",
            [tool.name for tool in tools],
        )

        return response.tools

    async def cleanup(self):
        """
        リソースのクリーンアップ

        非同期リソースやセッションなどのクリーンアップを行います。
        """
        await self.exit_stack.aclose()
        self.session = None
        self.stdio = None
        self.write = None
