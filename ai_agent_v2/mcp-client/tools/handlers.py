"""
ツール処理モジュール

MCPツールの呼び出しと結果処理を担当します
LangChain対応の機能を追加
"""

from typing import List

from core.utils import extract_tool_content, process_tool_arguments
from langchain_core.tools import BaseTool


class LangChainToolAdapter(BaseTool):
    """
    MCPツールをLangChainのツールとして使用するためのアダプタークラス
    """

    name: str
    description: str

    def __init__(self, name: str, description: str, tool_manager, tool_executor):
        """
        LangChainToolAdapterの初期化

        Args:
            name: ツール名
            description: ツール説明
            tool_manager: ToolManagerインスタンス
            tool_executor: ツール実行関数
        """
        super().__init__(name=name, description=description)
        # フィールドを直接設定 - Pydanticの検証をバイパス
        self._tool_manager = tool_manager
        self._tool_executor = tool_executor

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
        LangChainの非同期ツール実行インターフェースを実装

        Args:
            kwargs: ツールに渡す引数

        Returns:
            str: ツール実行結果
        """
        return await self._tool_executor(self.name, kwargs)


class ToolManager:
    """
    MCPツールの管理と実行を担当するクラス
    LangChain対応の機能を追加
    """

    def __init__(self, session, default_channel_id=None):
        """
        ToolManagerの初期化

        Args:
            session: MCPサーバーのセッション
            default_channel_id: デフォルトのSlackチャンネルID
        """
        self.session = session
        self.default_channel_id = default_channel_id
        self.langchain_tools = []  # LangChain用ツールリスト

    async def execute_tool(self, tool_name, tool_args):
        """
        ツール呼び出しを実行し、結果を処理

        Args:
            tool_name: 呼び出すツールの名前
            tool_args_dict: ツールに渡す引数

        Returns:
            str: 処理されたツール呼び出し結果
        """
        print(f"Calling tool {tool_name} with input type: {type(tool_args)}")
        print(f"Input content: {tool_args}")

        # Process tool arguments
        tool_args_dict = process_tool_arguments(
            tool_name, tool_args, self.default_channel_id
        )

        try:
            tool_result = await self.session.call_tool(tool_name, tool_args_dict)
            print(f"Tool result type: {type(tool_result.content)}")
            print(f"Tool result: {tool_result.content}")

            # Extract and process the content
            return extract_tool_content(tool_result.content)

        except Exception as e:
            error_msg = f"Error calling tool {tool_name}: {str(e)}"
            print(error_msg)
            return f"Error: {str(e)}"

    async def list_available_tools(self):
        """
        利用可能なツールのリストを取得

        Returns:
            list: 利用可能なツールのリスト
        """
        response = await self.session.list_tools()
        return response.tools

    async def create_langchain_tools(self) -> List[BaseTool]:
        """
        LangChain用のツールを生成

        Returns:
            List[BaseTool]: LangChain互換のツールリスト
        """
        tools = await self.list_available_tools()
        langchain_tools = []

        # ツール実行関数のクロージャを作成
        async def tool_executor(tool_name, args):
            return await self.execute_tool(tool_name, args)

        # 各ツールをLangChain形式に変換
        for tool in tools:
            langchain_tool = LangChainToolAdapter(
                name=tool.name,
                description=tool.description,
                tool_manager=self,
                tool_executor=tool_executor,
            )
            langchain_tools.append(langchain_tool)

        self.langchain_tools = langchain_tools
        return langchain_tools

    def get_langchain_tools(self) -> List[BaseTool]:
        """
        キャッシュされたLangChainツールリストを取得

        Returns:
            List[BaseTool]: LangChain互換のツールリスト
        """
        return self.langchain_tools
