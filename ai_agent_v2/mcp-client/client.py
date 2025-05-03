import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Optional

# Import both Anthropic and Google Gemini
import google.generativeai as genai
from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, stdio_client

load_dotenv()  # load environment variables from .env

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not found in environment variables")


class MCPClient:
    """
    MCPクライアントクラス - Model Context Protocol (MCP) サーバーとの通信を管理

    このクラスは、SlackやGitHubなどのMCPサーバーとの接続、
    大規模言語モデル(LLM)との統合、そしてユーザークエリの処理を行います。

    Attributes:
        session: MCP Serverとのセッションオブジェクト
        exit_stack: 非同期リソース管理用のコンテキストマネージャ
        model_provider: 使用するLLMプロバイダー（"anthropic"または"gemini"）
        anthropic: Claude APIクライアント
        gemini: Gemini APIクライアント
        current_server: 現在接続中のサーバー名
        default_channel_id: 設定ファイルから取得したデフォルトのSlackチャンネルID
    """

    def __init__(self, model_provider="gemini"):
        """
        MCPClientの初期化

        Args:
            model_provider: 使用するLLMプロバイダー（デフォルト: "gemini"）
                            "anthropic"または"gemini"が指定可能
        """
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model_provider = model_provider.lower()  # "anthropic" or "gemini"

        # Initialize model clients
        if self.model_provider == "anthropic":
            self.anthropic = Anthropic()
            self.gemini = None
        else:
            # Default to Gemini
            self.gemini = genai.GenerativeModel("gemini-1.5-pro")
            self.anthropic = None

        self.current_server = None
        # Default channel ID from schema if available
        self.default_channel_id = None

    async def connect_to_server(
        self, server_name: str = None, server_script_path: str = None
    ):
        """Connect to an MCP server using either a server name from schema or direct script path

        Args:
            server_name: Name of the server in the schema file (e.g., 'slack')
            server_script_path: Direct path to the server script (.py or .js)
        """
        if server_name and server_script_path:
            raise ValueError(
                "Provide either server_name OR server_script_path, not both"
            )

        if server_name:
            # Load from schema file
            schema_dir = os.path.join(os.path.dirname(__file__), "schema")
            schema_file = os.path.join(schema_dir, f"{server_name}.json")

            if not os.path.exists(schema_file):
                raise ValueError(
                    f"Schema file for {server_name} not found at {schema_file}"
                )

            with open(schema_file, "r") as f:
                schema = json.load(f)

            if server_name not in schema.get("mcpServers", {}):
                raise ValueError(f"Server '{server_name}' not found in schema file")

            server_config = schema["mcpServers"][server_name]
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", {})

            # Extract default channel ID if available in the environment variables
            if "SLACK_CHANNEL_IDS" in env:
                self.default_channel_id = env["SLACK_CHANNEL_IDS"].split(",")[0].strip()
                print(f"Default channel ID set to: {self.default_channel_id}")

            server_params = StdioServerParameters(command=command, args=args, env=env)
            self.current_server = server_name

        elif server_script_path:
            # Legacy method with direct script path
            is_python = server_script_path.endswith(".py")
            is_js = server_script_path.endswith(".js")
            if not (is_python or is_js):
                raise ValueError("Server script must be a .py or .js file")

            command = "python" if is_python else "node"
            server_params = StdioServerParameters(
                command=command, args=[server_script_path], env=None
            )
            self.current_server = "custom"
        else:
            raise ValueError("Must provide either server_name or server_script_path")

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(
            f"\nConnected to {self.current_server} server with tools:",
            [tool.name for tool in tools],
        )

    async def process_query(self, query: str) -> str:
        """
        ユーザークエリを処理し、適切なモデルとサーバーを使用して応答を生成

        このメソッドは、入力クエリを分析し、クロスサーバー操作が必要かどうかを判断します。
        クエリの内容に基づいて、適切なモデル（GeminiまたはClaude）での処理を選択します。

        Args:
            query: ユーザーから入力されたクエリ文字列

        Returns:
            str: モデルやツールによって生成された応答
        """
        # Get available tools in JSON Schema format
        response = await self.session.list_tools()

        # Add logic to handle multi-server operations
        if "github" in query.lower() and "slack" in query.lower():
            # This might be a cross-server operation
            return await self._process_cross_server_query(query)
        elif self.model_provider == "anthropic":
            # Format for Anthropic (Claude)
            return await self._process_with_anthropic(query, response.tools)
        else:
            # Format for Gemini
            return await self._process_with_gemini(query, response.tools)

    async def _process_cross_server_query(self, query: str) -> str:
        """
        複数のMCPサーバー間での操作を処理（GitHub → Slack）

        このメソッドは、GitHubからデータを取得し、そのデータをSlackに投稿するといった
        複数サーバーにまたがる操作を実行します。サーバー間の切り替えと元の状態への
        復帰も管理します。

        Args:
            query: ユーザーから入力されたクエリ文字列

        Returns:
            str: 処理の各段階とその結果を示す文字列
        """
        # Store current connection
        original_server = self.current_server
        original_session = self.session

        result_text = []
        result_text.append("複数サーバー間の操作を実行します...")

        try:
            # Step 1: Connect to GitHub
            result_text.append("GitHubサーバーに接続中...")
            try:
                await self.connect_to_server(server_name="github")
                result_text.append("GitHub接続成功")

                # Step 2: Get GitHub information
                # Example: get repo list, issues, etc.
                # This would require parsing the query to determine what GitHub info to fetch
                github_info = await self._extract_github_info(query)
                result_text.append(f"GitHub情報取得: {github_info}")

                # Step 3: Reconnect to Slack
                await self.cleanup()  # Close GitHub connection
                result_text.append("Slackサーバーに再接続中...")
                await self.connect_to_server(server_name="slack")
                result_text.append("Slack接続成功")

                # Step 4: Post to Slack
                if self.default_channel_id:
                    post_result = await self._post_to_slack(github_info)
                    result_text.append(f"Slack投稿結果: {post_result}")
                else:
                    result_text.append(
                        "デフォルトのSlackチャンネルが設定されていません"
                    )

            except Exception as e:
                result_text.append(f"エラー発生: {str(e)}")

            # Reconnect to original server if needed
            if original_server != self.current_server:
                await self.cleanup()
                if original_server == "slack":
                    await self.connect_to_server(server_name="slack")
                elif original_server == "github":
                    await self.connect_to_server(server_name="github")

            return "\n".join(result_text)
        except Exception as e:
            return f"サーバー間操作中にエラーが発生しました: {str(e)}"

    async def _extract_github_info(self, query: str) -> str:
        """
        GitHubからクエリに基づいて情報を抽出

        このメソッドは、GitHub MCPサーバーを介してGitHubから情報を取得します。
        利用可能なGitHubツールを検出し、適切なツールを使用して情報を取得します。

        Args:
            query: 情報抽出のためのクエリ

        Returns:
            str: GitHubから取得した情報
        """
        # This is a placeholder - actual implementation would parse query
        # and use GitHub tools to fetch relevant information

        # Example: List repositories
        try:
            # Check available GitHub tools
            response = await self.session.list_tools()
            tools = [tool.name for tool in response.tools]

            if "github_list_repos" in tools:
                result = await self.session.call_tool("github_list_repos", {})
                return self._extract_tool_content(result.content)
            elif "github_get_user" in tools:
                result = await self.session.call_tool("github_get_user", {})
                return self._extract_tool_content(result.content)
            else:
                return "利用可能なGitHubツールが見つかりませんでした"
        except Exception as e:
            return f"GitHub情報取得エラー: {str(e)}"

    async def _post_to_slack(self, content: str) -> str:
        """
        Slackチャンネルに内容を投稿

        このメソッドは、Slack MCPサーバーを介してSlackチャンネルに
        与えられたコンテンツを投稿します。デフォルトのチャンネルIDが
        設定されていない場合はエラーを返します。

        Args:
            content: Slackに投稿する内容

        Returns:
            str: 投稿結果のメッセージ
        """
        try:
            if not self.default_channel_id:
                return "デフォルトのSlackチャンネルIDが設定されていません"

            message = f"GitHubから取得した情報:\n```\n{content}\n```"
            result = await self.session.call_tool(
                "slack_post_message",
                {"channel_id": self.default_channel_id, "text": message},
            )

            return self._extract_tool_content(result.content)
        except Exception as e:
            return f"Slack投稿エラー: {str(e)}"

    def _extract_tool_content(self, content):
        """
        ツール応答からテキストコンテンツを抽出

        このメソッドは、ツール呼び出しの結果からテキストコンテンツを抽出します。
        TextContentオブジェクトのリストや、他の複雑な構造を扱うことができます。

        Args:
            content: ツール呼び出しの結果

        Returns:
            str: 抽出されたテキストコンテンツ
        """
        if hasattr(content, "__iter__") and not isinstance(content, str):
            # It's an iterable of TextContent objects
            result_texts = []
            for item in content:
                if hasattr(item, "text"):
                    result_texts.append(item.text)
            return "".join(result_texts)
        else:
            # It's a single value
            return str(content)

    async def _process_with_anthropic(self, query, mcp_tools):
        """
        Anthropic Claude LLMを使用してクエリを処理

        このメソッドは、Claude APIを使用してユーザークエリを処理します。
        MCPツールをClaude APIが理解できるフォーマットに変換し、
        ツール使用を含む応答を生成します。

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト

        Returns:
            str: Claudeの応答
        """
        # Format tools for Claude
        tools_json = []
        for tool in mcp_tools:
            # Handle inputSchema - may already be parsed JSON object or a string
            try:
                input_schema = (
                    json.loads(tool.inputSchema)
                    if isinstance(tool.inputSchema, str)
                    else tool.inputSchema
                )
            except (TypeError, json.JSONDecodeError):
                input_schema = {"type": "object", "properties": {}}

            tool_json = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": input_schema,
            }
            tools_json.append(tool_json)

        # Initial message to Claude
        messages = [{"role": "user", "content": query}]

        # Claude API call
        try:
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                tools=tools_json,
            )

            # Process Claude response
            return await self._process_claude_response(response, messages, tools_json)
        except Exception as e:
            print(f"Error calling Claude API: {str(e)}")
            return f"Error with Claude API: {str(e)}"

    async def _process_with_gemini(self, query, mcp_tools):
        """
        Google Gemini LLMを使用してクエリを処理（簡易アプローチ）

        このメソッドは、Gemini APIを使用してユーザークエリを処理します。
        ツールを直接呼び出す代わりに、利用可能なツールに関する情報を含む
        プロンプトを構築し、シンプルなテキスト応答を生成します。

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト

        Returns:
            str: Geminiの応答
        """
        try:
            # Simple approach without trying to use tools
            gemini_prompt = f"""あなたはSlackに接続された日本語で対応するアシスタントです。
Slackの統合でできることをユーザーに説明することができます。
以下のSlackツールが利用可能です: {", ".join([tool.name for tool in mcp_tools])}

ユーザーの質問: {query}

ユーザーの質問に直接答えてください。簡易モードで実行されていることを日本語で説明してください。
日本語で丁寧に回答してください。
"""

            response = self.gemini.generate_content(
                contents=gemini_prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 800},
            )

            return response.text
        except Exception as e:
            print(f"Error with Gemini API: {str(e)}")
            return f"申し訳ありません。リクエスト処理中にエラーが発生しました: {str(e)}"

    async def _process_claude_response(self, response, messages, tools_json):
        """
        Claude APIからの応答を処理

        このメソッドは、Claude APIからの応答を処理し、テキスト内容の抽出や
        ツール呼び出しの実行を行います。応答が複数のツール呼び出しを含む場合、
        それぞれのツール呼び出しを処理し、その結果をClaudeに返して会話を継続します。

        Args:
            response: Claude APIのレスポンスオブジェクト
            messages: 会話履歴
            tools_json: 利用可能なツールの定義（JSON形式）

        Returns:
            str: 最終的なテキスト応答
        """
        final_text = []
        conversation_history = messages.copy()

        while True:
            # Extract text content
            assistant_message = {"role": "assistant", "content": []}
            has_tool_use = False

            for content in response.content:
                if content.type == "text":
                    final_text.append(content.text)
                    assistant_message["content"].append(
                        {"type": "text", "text": content.text}
                    )
                elif content.type == "tool_use":
                    has_tool_use = True
                    # Handle the Claude API format for tool calls
                    tool_name = content.name
                    tool_args = content.input
                    tool_id = content.id

                    # Format tool_use correctly
                    assistant_message["content"].append(
                        {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool_name,
                            "input": tool_args,
                        }
                    )

                    # Process tool arguments
                    tool_args_dict = self._process_tool_arguments(tool_name, tool_args)

                    # Execute tool call
                    result_content = await self._execute_tool_call(
                        tool_name, tool_args_dict
                    )

                    # Add tool result to conversation
                    conversation_history.append(assistant_message)
                    conversation_history.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": result_content
                                    if isinstance(result_content, str)
                                    else json.dumps(result_content),
                                }
                            ],
                        }
                    )

                    # Get next response from Claude
                    response = self.anthropic.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        messages=conversation_history,
                        tools=tools_json,
                    )

                    # Continue processing the new response
                    break
            else:
                # No tool calls in this response, we're done
                conversation_history.append(assistant_message)
                # If we never had any tool calls, just return the text
                if not has_tool_use:
                    print("No tool calls were made, returning direct response")
                break

        return "\n".join(final_text)

    def _process_tool_arguments(self, tool_name, tool_args):
        """
        ツール引数を処理し、実行のために準備

        このメソッドは、ツール呼び出しのための引数を適切な形式に変換します。
        文字列の解析、デフォルトチャンネルIDの追加などの処理を行います。

        Args:
            tool_name: 呼び出すツールの名前
            tool_args: ツールに渡す引数（文字列または辞書）

        Returns:
            dict: 処理された引数辞書
        """
        if isinstance(tool_args, str) and tool_args.strip() == "{}":
            # Empty JSON object as string - convert to empty dict
            tool_args_dict = {}
        elif isinstance(tool_args, str) and tool_args.strip().startswith("{"):
            # Try to parse as JSON string
            try:
                tool_args_dict = json.loads(tool_args)
            except json.JSONDecodeError:
                tool_args_dict = {"text": tool_args}
        else:
            # Already a dict or other input
            tool_args_dict = (
                tool_args if isinstance(tool_args, dict) else {"text": tool_args}
            )

        # Add default channel_id if available and needed for Slack tools
        if self.default_channel_id and "channel_id" not in tool_args_dict:
            if tool_name.startswith("slack_") and (
                "channel" in tool_name
                or tool_name == "slack_post_message"
                or tool_name == "slack_reply_to_thread"
            ):
                tool_args_dict["channel_id"] = self.default_channel_id
                print(f"Using default channel ID: {self.default_channel_id}")

        # For slack_post_message, make sure we have text
        if tool_name == "slack_post_message" and "text" not in tool_args_dict:
            # Try to extract text from context
            if isinstance(tool_args, str) and not tool_args.startswith("{"):
                tool_args_dict["text"] = tool_args.strip()
            print(f"Message text: {tool_args_dict.get('text', 'None')}")

        return tool_args_dict

    async def _execute_tool_call(self, tool_name, tool_args_dict):
        """
        ツール呼び出しを実行し、結果を処理

        このメソッドは、MCPサーバーにツール呼び出しをリクエストし、
        返された結果を処理します。TextContentオブジェクトなど
        複雑な結果形式も適切に処理します。

        Args:
            tool_name: 呼び出すツールの名前
            tool_args_dict: ツールに渡す引数の辞書

        Returns:
            str: 処理されたツール呼び出し結果
        """
        print(f"Calling tool {tool_name} with input type: {type(tool_args_dict)}")
        print(f"Input content: {tool_args_dict}")

        try:
            tool_result = await self.session.call_tool(tool_name, tool_args_dict)
            print(f"Tool result type: {type(tool_result.content)}")
            print(f"Tool result: {tool_result.content}")

            # Extract and process the content properly, handling TextContent objects
            result_content = None
            if hasattr(tool_result.content, "__iter__") and not isinstance(
                tool_result.content, str
            ):
                # It's an iterable of TextContent objects
                result_texts = []
                for item in tool_result.content:
                    if hasattr(item, "text"):
                        result_texts.append(item.text)
                # Join and parse if it looks like JSON
                combined_text = "".join(result_texts)
                result_content = combined_text
            else:
                # It's a single value
                result_content = tool_result.content

            return result_content

        except Exception as e:
            error_msg = f"Error calling tool {tool_name}: {str(e)}"
            print(error_msg)
            return f"Error: {str(e)}"

    async def chat_loop(self):
        """
        対話型チャットループを実行

        ユーザーからの入力を受け取り、応答を生成する対話型ループを実行します。
        'quit'と入力されるまで継続します。

        Returns:
            None
        """
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        print(f"Using model provider: {self.model_provider}")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """
        リソースのクリーンアップ

        非同期リソースやセッションなどのクリーンアップを行います。
        プログラム終了時や接続切り替え時に呼び出されます。

        Returns:
            None
        """
        await self.exit_stack.aclose()


async def main():
    """
    メインの実行関数

    コマンドライン引数を解析し、適切なモデルとサーバーでMCPクライアントを起動します。

    Returns:
        None
    """
    import argparse

    parser = argparse.ArgumentParser(description="MCP Client")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server", "-s", help="Server name from schema (e.g., slack)")
    group.add_argument("--path", "-p", help="Path to server script file")
    parser.add_argument(
        "--model",
        "-m",
        default="gemini",
        choices=["gemini", "anthropic"],
        help="Model provider to use (default: gemini)",
    )
    args = parser.parse_args()

    client = MCPClient(model_provider=args.model)
    try:
        if args.server:
            await client.connect_to_server(server_name=args.server)
        else:
            await client.connect_to_server(server_script_path=args.path)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
