"""
ツール処理モジュール

MCPツールの呼び出しと結果処理を担当します
"""

from ..core.utils import extract_tool_content, process_tool_arguments


class ToolManager:
    """
    MCPツールの管理と実行を担当するクラス
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
