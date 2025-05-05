"""
セッション管理モジュール

MCPサーバーとの接続と設定を管理します
LangChain対応の機能を追加
"""

from config import extract_default_channel_id, get_server_config, load_server_schema
from langchain_core.tools import BaseTool
from mcp import StdioServerParameters

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


class MCPToolWrapper(BaseTool):
    """
    MCPツールをLangChainのToolとして利用するためのラッパークラス
    """

    name: str
    description: str

    def __init__(self, name, description, session, tool_args_processor):
        """
        MCPToolWrapperの初期化

        Args:
            name: ツール名
            description: ツールの説明
            session: MCPサーバーセッション
            tool_args_processor: 引数処理関数
        """
        # スーパークラスの初期化
        super().__init__(name=name, description=description)
        # フィールドを直接設定 - Pydanticの検証をバイパス
        self._session = session
        self._tool_processor = tool_args_processor

    def _run(self, **kwargs) -> str:
        """
        ツールの同期実行（LangChain Toolsインターフェースの実装）
        BaseTool抽象クラスの要件を満たすために必要だが、実際には非同期版のみ使用

        Args:
            kwargs: ツールに渡す引数

        Returns:
            str: エラーメッセージ
        """
        # 同期版は実際には使用しないが、抽象クラスの要件を満たすために実装
        return "This tool only supports async execution with _arun"

    async def _arun(self, **kwargs) -> str:
        """
        ツールの非同期実行（LangChain Toolsインターフェースの実装）

        Args:
            kwargs: ツールに渡す引数

        Returns:
            str: ツール実行結果
        """
        from core.utils import extract_tool_content

        # 引数の処理
        tool_args_dict = self._tool_processor(self.name, kwargs)

        try:
            # ツールの実行
            tool_result = await self._session.call_tool(self.name, tool_args_dict)

            # 結果の抽出と処理
            return extract_tool_content(tool_result.content)
        except Exception as e:
            error_msg = f"Error calling tool {self.name}: {str(e)}"
            print(error_msg)
            return f"Error: {str(e)}"


class SessionManager(BaseMCPClient):
    """
    MCPサーバーとのセッションを管理
    LangChain対応の機能を追加
    """

    def __init__(self):
        """
        SessionManagerの初期化
        """
        super().__init__()
        self.langchain_tools = []

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
        tools = await self.connect_to_server(server_params, server_name)

        # LangChain用のツールラッパーを準備
        await self.prepare_langchain_tools(tools)

        return tools

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
        tools = await self.connect_to_server(server_params, "custom")

        # LangChain用のツールラッパーを準備
        await self.prepare_langchain_tools(tools)

        return tools

    async def prepare_langchain_tools(self, mcp_tools):
        """
        MCPツールをLangChain用のツールラッパーに変換
        """
        from core.utils import process_tool_arguments

        self.langchain_tools = []

        for tool in mcp_tools:
            # 引数処理関数
            def create_tool_processor(tool_name):
                def processor(_, args):
                    return process_tool_arguments(
                        tool_name, args, self.default_channel_id
                    )

                return processor

            tool_processor = create_tool_processor(tool.name)

            # 新しいツールラッパーを作成
            langchain_tool = MCPToolWrapper(
                name=tool.name,
                description=tool.description,
                session=self.session,  # self ではなく self.session を渡す
                tool_args_processor=tool_processor,
            )

            self.langchain_tools.append(langchain_tool)

    def get_langchain_tools(self):
        """
        LangChain用のツールリストを取得

        Returns:
            list: LangChain形式のツールリスト
        """
        return self.langchain_tools
