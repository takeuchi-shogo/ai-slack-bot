"""
セッション管理モジュール

MCPサーバーとの接続と設定を管理します
"""

from mcp import StdioServerParameters

from ..config import extract_default_channel_id, get_server_config, load_server_schema
from .base import BaseMCPClient


class ServerConnector:
    """
    MCPサーバーへの接続を管理するクラス
    """

    @staticmethod
    def create_server_params_from_name(server_name):
        """
        サーバー名からサーバーパラメータを作成

        Args:
            server_name: サーバーの名前

        Returns:
            tuple: (StdioServerParameters, default_channel_id)
        """
        schema = load_server_schema(server_name)
        server_config = get_server_config(schema, server_name)

        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        # Extract default channel ID if available in the environment variables
        default_channel_id = extract_default_channel_id(env)
        if default_channel_id:
            print(f"Default channel ID set to: {default_channel_id}")

        return StdioServerParameters(
            command=command, args=args, env=env
        ), default_channel_id

    @staticmethod
    def create_server_params_from_script(server_script_path):
        """
        スクリプトパスからサーバーパラメータを作成

        Args:
            server_script_path: サーバースクリプトのパス

        Returns:
            StdioServerParameters
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        return StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )


class SessionManager(BaseMCPClient):
    """
    MCPサーバーとのセッションを管理
    """

    async def connect_to_server_by_name(self, server_name):
        """
        サーバー名を使用してMCPサーバーに接続

        Args:
            server_name: サーバーの名前

        Returns:
            list: 利用可能なツールのリスト
        """
        server_params, default_channel_id = (
            ServerConnector.create_server_params_from_name(server_name)
        )
        self.default_channel_id = default_channel_id
        return await self.connect_to_server(server_params, server_name)

    async def connect_to_server_by_script(self, server_script_path):
        """
        スクリプトパスを使用してMCPサーバーに接続

        Args:
            server_script_path: サーバースクリプトのパス

        Returns:
            list: 利用可能なツールのリスト
        """
        server_params = ServerConnector.create_server_params_from_script(
            server_script_path
        )
        return await self.connect_to_server(server_params, "custom")
