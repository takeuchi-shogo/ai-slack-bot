"""
MCPクライアントメインモジュール

Model Context Protocol (MCP) サーバーとの通信と連携を管理する
メインクラスと実行エントリーポイントを提供します
"""
import asyncio
import argparse
from typing import Optional

# Core modules
from core.session import SessionManager
from tools.handlers import ToolManager

# Model handlers
from models.anthropic import AnthropicModelHandler
from models.gemini import GeminiModelHandler

# Services
from services.github import GitHubService
from services.notion import NotionService
from services.slack import SlackService

class MCPClient:
    """
    MCPクライアントクラス - Model Context Protocol (MCP) サーバーとの通信を管理

    このクラスは、SlackやGitHubなどのMCPサーバーとの接続、
    大規模言語モデル(LLM)との統合、そしてユーザークエリの処理を行います。

    Attributes:
        session_manager: MCPサーバーとのセッション管理
        model_provider: 使用するLLMプロバイダー（"anthropic"または"gemini"）
        anthropic_handler: Claude APIハンドラ
        gemini_handler: Gemini APIハンドラ
        tool_manager: ツール管理インスタンス
        github_service: GitHubサービス
        notion_service: Notionサービス
        slack_service: Slackサービス
    """

    def __init__(self, model_provider="gemini"):
        """
        MCPClientの初期化

        Args:
            model_provider: 使用するLLMプロバイダー（デフォルト: "gemini"）
                            "anthropic"または"gemini"が指定可能
        """
        self.model_provider = model_provider.lower()  # "anthropic" or "gemini"
        self.session_manager = SessionManager()
        self.tool_manager = None
        
        # Initialize model handlers
        if self.model_provider == "anthropic":
            self.anthropic_handler = AnthropicModelHandler()
            self.gemini_handler = None
        else:
            # Default to Gemini
            self.gemini_handler = GeminiModelHandler()
            self.anthropic_handler = None
            
        # Services will be initialized after server connection
        self.github_service = None
        self.notion_service = None
        self.slack_service = None

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
            # Connect using server name from schema
            tools = await self.session_manager.connect_to_server_by_name(server_name)
        elif server_script_path:
            # Connect using script path
            tools = await self.session_manager.connect_to_server_by_script(server_script_path)
        else:
            raise ValueError("Must provide either server_name or server_script_path")

        # Initialize tool manager
        self.tool_manager = ToolManager(
            self.session_manager.session, 
            self.session_manager.default_channel_id
        )
        
        # Initialize services
        self.github_service = GitHubService(self.tool_manager)
        self.notion_service = NotionService(self.tool_manager)
        self.slack_service = SlackService(
            self.tool_manager, 
            self.session_manager.default_channel_id
        )

    async def process_query(
        self, query: str, thread_ts: str = None, user_id: str = None
    ) -> str:
        """
        ユーザークエリを処理し、適切なモデルとサーバーを使用して応答を生成

        このメソッドは、入力クエリを分析し、クロスサーバー操作が必要かどうかを判断します。
        クエリの内容に基づいて、適切なモデル（GeminiまたはClaude）での処理を選択します。

        Args:
            query: ユーザーから入力されたクエリ文字列
            thread_ts: メッセージのスレッドタイムスタンプ（スレッド返信の場合）
            user_id: ユーザーID（メンション付き返信の場合）

        Returns:
            str: モデルやツールによって生成された応答
        """
        # Get available tools in JSON Schema format
        tools = await self.tool_manager.list_available_tools()

        # Add logic to handle multi-server operations
        if (
            ("github" in query.lower() and "slack" in query.lower())
            or ("github" in query.lower() and "notion" in query.lower())
            or ("コード検索" in query and "タスク" in query)
            or ("問題" in query and "修正" in query)
        ):
            # This might be a cross-server operation
            return await self._process_cross_server_query(query, thread_ts, user_id)
        elif self.model_provider == "anthropic":
            # Process with Anthropic (Claude)
            async def tool_executor(tool_name, tool_args):
                return await self.tool_manager.execute_tool(tool_name, tool_args)
            
            result = await self.anthropic_handler.process_query(
                query, tools, tool_executor
            )

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.session_manager.current_server == "slack":
                await self.slack_service.reply_to_slack_thread(result, thread_ts, user_id)

            return result
        else:
            # Process with Gemini
            result = await self.gemini_handler.process_query(
                query, tools, self.session_manager.default_channel_id
            )

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.session_manager.current_server == "slack":
                await self.slack_service.reply_to_slack_thread(result, thread_ts, user_id)

            return result

    async def _process_cross_server_query(
        self, query: str, thread_ts: str = None, user_id: str = None
    ) -> str:
        """
        複数のMCPサーバー間での操作を処理（GitHub → Notion → Slack）

        このメソッドは、GitHubからコード情報を取得し、問題があればNotionにタスクを作成し、
        その結果をSlackに投稿する複数サーバーにまたがる操作を実行します。
        サーバー間の切り替えと元の状態への復帰も管理します。

        Args:
            query: ユーザーから入力されたクエリ文字列
            thread_ts: Slackスレッドのタイムスタンプ（スレッド返信の場合）
            user_id: SlackユーザーID（メンション付き返信の場合）

        Returns:
            str: 処理の各段階とその結果を示す文字列
        """
        # Store current connection
        original_server = self.session_manager.current_server
        
        result_text = []
        result_text.append("複数サーバー間の操作を実行します...")

        try:
            # Step 1: Connect to GitHub
            result_text.append("GitHubサーバーに接続中...")
            try:
                await self.connect_to_server(server_name="github")
                result_text.append("GitHub接続成功")

                # Step 2: Get GitHub information & analyze code issues
                github_info = await self.github_service.extract_github_info(query)
                result_text.append(f"GitHub情報取得: {github_info}")

                # Check if code issues were found that need tasks
                need_task_creation = (
                    "問題" in github_info
                    or "バグ" in github_info
                    or "修正" in github_info
                )
                notion_task_info = None

                # Step 3: Connect to Notion if we need to create tasks
                if need_task_creation:
                    await self.cleanup()  # Close GitHub connection
                    result_text.append("Notionサーバーに接続中...")
                    await self.connect_to_server(server_name="notionApi")
                    result_text.append("Notion接続成功")

                    # Create task in Notion
                    notion_task_info = await self.notion_service.create_notion_task(
                        github_info, query
                    )
                    result_text.append(f"Notionタスク作成結果: {notion_task_info}")

                # Step 4: Reconnect to Slack to post the summary
                await self.cleanup()  # Close current connection
                result_text.append("Slackサーバーに接続中...")
                await self.connect_to_server(server_name="slack")
                result_text.append("Slack接続成功")

                # Step 5: Post to Slack with combined info
                if self.session_manager.default_channel_id:
                    # Prepare summary message including GitHub findings and Notion task if created
                    summary = f"GitHubコード分析結果:\n{github_info}"
                    if notion_task_info:
                        summary += f"\n\nNotionタスク作成:\n{notion_task_info}"

                    # If we have thread info, reply to thread
                    if thread_ts and user_id:
                        post_result = await self.slack_service.reply_to_slack_thread(
                            summary, thread_ts, user_id
                        )
                        result_text.append(f"Slackスレッドへの返信結果: {post_result}")
                    else:
                        # Otherwise post as a new message
                        post_result = await self.slack_service.post_to_slack(summary)
                        result_text.append(f"Slack投稿結果: {post_result}")
                else:
                    result_text.append(
                        "デフォルトのSlackチャンネルが設定されていません"
                    )

            except Exception as e:
                result_text.append(f"エラー発生: {str(e)}")

            # Reconnect to original server if needed
            if original_server != self.session_manager.current_server:
                await self.cleanup()
                if original_server:
                    await self.connect_to_server(server_name=original_server)

            return "\n".join(result_text)
        except Exception as e:
            return f"サーバー間操作中にエラーが発生しました: {str(e)}"

    async def chat_loop(self, thread_ts=None, user_id=None):
        """
        対話型チャットループを実行

        ユーザーからの入力を受け取り、応答を生成する対話型ループを実行します。
        'quit'と入力されるまで継続します。

        Args:
            thread_ts: Slackスレッドのタイムスタンプ（CLIでは使用しない）
            user_id: SlackユーザーID（CLIでは使用しない）

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

                response = await self.process_query(query, thread_ts, user_id)
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
        await self.session_manager.cleanup()
        # Reset services
        self.tool_manager = None
        self.github_service = None
        self.notion_service = None
        self.slack_service = None


async def main():
    """
    メインの実行関数

    コマンドライン引数を解析し、適切なモデルとサーバーでMCPクライアントを起動します。
    スレッド情報やユーザーIDも指定可能で、Slackの自動化スクリプトからも呼び出せます。

    Returns:
        None
    """
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
    parser.add_argument(
        "--thread",
        "-t",
        help="Slack thread timestamp for thread replies",
    )
    parser.add_argument(
        "--user",
        "-u",
        help="Slack user ID to mention in replies",
    )
    parser.add_argument(
        "--query",
        "-q",
        help="Direct query to process (non-interactive mode)",
    )
    args = parser.parse_args()

    client = MCPClient(model_provider=args.model)
    try:
        if args.server:
            await client.connect_to_server(server_name=args.server)
        else:
            await client.connect_to_server(server_script_path=args.path)

        # Check if we're in non-interactive mode
        if args.query:
            # Process single query and exit
            result = await client.process_query(args.query, args.thread, args.user)
            print(result)
        else:
            # Start interactive chat loop
            await client.chat_loop(args.thread, args.user)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())