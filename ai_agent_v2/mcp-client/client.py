"""
MCPクライアントメインモジュール

Model Context Protocol (MCP) サーバーとの通信と連携を管理する
メインクラスと実行エントリーポイントを提供します
LangChainを使用したAIエージェントに対応
LangGraphを使用したマルチエージェントシステムに対応
データベースへの自然言語クエリ機能を含む
"""

import argparse
import asyncio
import logging
from enum import Enum

# Core modules
from core.graph import GraphManager
from core.session import SessionManager
from database.agent import DatabaseQueryAgent

# Database modules
from database.connection import DatabaseConnection

# LangChain dependencies
from langchain_core.messages import AIMessage, HumanMessage

# Model handlers
from models.anthropic import AnthropicModelHandler
from models.gemini import GeminiModelHandler

# Services
from services.github import GitHubService
from services.notion import NotionService
from services.slack import SlackService
from tools.handlers import ToolManager

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class ConnectionMode(Enum):
    """接続モードを定義する列挙型"""

    SIMPLE = "simple"  # 簡易モード (スクリプトを直接実行)
    FULL = "full"  # 完全モード (MCPサーバーに接続)


class OperationMode(Enum):
    """操作モードを定義する列挙型"""

    LANGCHAIN = "langchain"  # LangChainを使用した単一エージェントモード
    LANGGRAPH = "langgraph"  # LangGraphを使用したマルチエージェントモード


class MCPClient:
    """
    MCPクライアントクラス - Model Context Protocol (MCP) サーバーとの通信を管理

    このクラスは、SlackやGitHubなどのMCPサーバーとの接続、
    大規模言語モデル(LLM)との統合、そしてユーザークエリの処理を行います。
    データベースへの自然言語クエリ機能もサポートしています。
    LangGraphを使用したマルチエージェントシステムにも対応しています。

    Attributes:
        session_manager: MCPサーバーとのセッション管理
        model_provider: 使用するLLMプロバイダー（"anthropic"または"gemini"）
        connection_mode: 接続モード（"simple"または"full"）
        operation_mode: 操作モード（"langchain"または"langgraph"）
        anthropic_handler: Claude APIハンドラ
        gemini_handler: Gemini APIハンドラ
        tool_manager: ツール管理インスタンス
        github_service: GitHubサービス
        notion_service: Notionサービス
        slack_service: Slackサービス
        db_connection: データベース接続
        db_agent: データベースクエリエージェント
        graph_manager: LangGraphグラフ管理インスタンス
    """

    def __init__(
        self,
        model_provider="anthropic",
        connection_mode=ConnectionMode.FULL,
        operation_mode=OperationMode.LANGGRAPH,
    ):
        """
        MCPClientの初期化
        LangChain/LangGraph対応のモデルハンドラーを初期化

        Args:
            model_provider: 使用するLLMプロバイダー（デフォルト: "anthropic"）
                            "anthropic"または"gemini"が指定可能
            connection_mode: 接続モード（デフォルト: ConnectionMode.FULL）
                             ConnectionMode.SIMPLE（簡易モード）またはConnectionMode.FULL（完全モード）
            operation_mode: 操作モード（デフォルト: OperationMode.LANGGRAPH）
                            OperationMode.LANGCHAIN（単一エージェント）または
                            OperationMode.LANGGRAPH（マルチエージェント）
        """
        self.model_provider = model_provider.lower()  # "anthropic" or "gemini"
        self.connection_mode = connection_mode
        self.operation_mode = operation_mode
        self.session_manager = SessionManager()
        self.tool_manager = None

        # 会話履歴の追跡用（LangChain対応）
        self.conversation_history = []

        # DB関連の初期化
        self.db_connection = DatabaseConnection()
        self.db_agent = None

        # LangGraph関連の初期化
        self.graph_manager = None

        # モデルハンドラーを初期化
        if self.model_provider == "anthropic":
            self.anthropic_handler = AnthropicModelHandler()
            self.gemini_handler = None
            print("LangChain対応のAnthropicモデルハンドラーを初期化しました")
        else:
            # Default to Gemini
            self.gemini_handler = GeminiModelHandler()
            self.anthropic_handler = None
            print("LangChain対応のGeminiモデルハンドラーを初期化しました")

        # Services will be initialized after server connection
        self.github_service = None
        self.notion_service = None
        self.slack_service = None

    async def initialize_database(self):
        """データベース関連の機能を初期化"""
        try:
            # データベースに接続
            connected = await self.db_connection.connect()
            if not connected:
                logging.warning(
                    "データベースに接続できませんでした。データベース機能は無効になります。"
                )
                return False

            # 使用するLLMを取得
            llm = (
                self.anthropic_handler.llm
                if self.model_provider == "anthropic"
                else self.gemini_handler.llm
            )

            # データベースエージェントを初期化
            self.db_agent = DatabaseQueryAgent(llm, self.db_connection)
            await self.db_agent.initialize()

            logging.info("データベース機能が初期化されました")
            return True
        except Exception as e:
            logging.error(f"データベース初期化エラー: {str(e)}")
            return False

    async def initialize_graph_manager(self):
        """LangGraphマネージャーを初期化"""
        try:
            # 使用するLLMを取得
            llm = (
                self.anthropic_handler.llm
                if self.model_provider == "anthropic"
                else self.gemini_handler.llm
            )

            # LangGraphマネージャーを初期化
            self.graph_manager = GraphManager(
                model_provider=self.model_provider,
                tool_manager=self.tool_manager,
                db_connection=self.db_connection,
            )

            # LangGraphを構築
            await self.graph_manager.build_graph()

            logging.info("LangGraphマネージャーが初期化されました")
            return True
        except Exception as e:
            logging.error(f"LangGraphマネージャー初期化エラー: {str(e)}")
            return False

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
            tools = await self.session_manager.connect_to_server_by_script(
                server_script_path
            )
        else:
            raise ValueError("Must provide either server_name or server_script_path")

        # Initialize tool manager
        self.tool_manager = ToolManager(
            self.session_manager.session, self.session_manager.default_channel_id
        )

        # Initialize services
        self.github_service = GitHubService(self.tool_manager)
        self.notion_service = NotionService(self.tool_manager)
        self.slack_service = SlackService(
            self.tool_manager, self.session_manager.default_channel_id
        )

        # LangGraphモードの場合はグラフマネージャーを初期化
        if self.operation_mode == OperationMode.LANGGRAPH:
            await self.initialize_graph_manager()

    async def process_query(
        self, query: str, thread_ts: str = None, user_id: str = None
    ) -> str:
        """
        ユーザークエリを処理し、適切なモデルとモードで応答を生成

        LangChainモードとLangGraphモードによって処理が分岐します

        Args:
            query: ユーザーから入力されたクエリ文字列
            thread_ts: メッセージのスレッドタイムスタンプ（スレッド返信の場合）
            user_id: ユーザーID（メンション付き返信の場合）

        Returns:
            str: モデルやツールによって生成された応答
        """
        # 会話履歴に追加
        self.conversation_history.append(HumanMessage(content=query))

        # LangGraphモードで処理
        if self.operation_mode == OperationMode.LANGGRAPH:
            return await self._process_query_with_langgraph(query, thread_ts, user_id)

        # LangChainモードで処理
        return await self._process_query_with_langchain(query, thread_ts, user_id)

    async def _process_query_with_langgraph(
        self, query: str, thread_ts: str = None, user_id: str = None
    ) -> str:
        """
        LangGraphモードを使用してクエリを処理

        マルチエージェントによる協調処理を行います

        Args:
            query: ユーザーから入力されたクエリ文字列
            thread_ts: メッセージのスレッドタイムスタンプ（スレッド返信の場合）
            user_id: ユーザーID（メンション付き返信の場合）

        Returns:
            str: マルチエージェントシステムによって生成された応答
        """
        logging.info(f"LangGraphモードでクエリを処理: {query}")

        # グラフマネージャーがない場合は初期化
        if not self.graph_manager:
            await self.initialize_graph_manager()

        # グラフを使用してクエリを処理
        result = await self.graph_manager.process_query(query, user_id, thread_ts)

        # 結果から応答を取得
        response = result.get("response", "応答が生成されませんでした")

        # 応答を会話履歴に追加
        self.conversation_history.append(AIMessage(content=response))

        return response

    async def _process_query_with_langchain(
        self, query: str, thread_ts: str = None, user_id: str = None
    ) -> str:
        """
        LangChainモードを使用してクエリを処理

        単一エージェントによる処理を行います（従来の実装方式）

        Args:
            query: ユーザーから入力されたクエリ文字列
            thread_ts: メッセージのスレッドタイムスタンプ（スレッド返信の場合）
            user_id: ユーザーID（メンション付き返信の場合）

        Returns:
            str: LangChainモデルによって生成された応答
        """
        logging.info(f"LangChainモードでクエリを処理: {query}")

        # データベースクエリの検出と処理
        if self.db_agent:
            try:
                # データベースクエリかどうかを判断
                is_db_query = await self.db_agent.is_database_query(query)

                if is_db_query:
                    logging.info(f"データベースクエリと判断されました: {query}")

                    # データベースクエリを処理
                    db_result = await self.db_agent.process_query(query)

                    # 結果に基づいて応答を生成
                    if "error" in db_result:
                        result = f"データベースクエリ処理中にエラーが発生しました: {db_result['error']}"
                    else:
                        if "explanation" in db_result:
                            result = db_result["explanation"]
                        else:
                            result = f"クエリの結果: {db_result['raw_result']}"

                    # 応答を会話履歴に追加
                    self.conversation_history.append(AIMessage(content=result))
                    return result
            except Exception as e:
                logging.error(f"データベースクエリ処理エラー: {str(e)}")
                # エラーが発生した場合は標準の処理に戻る

        # 簡易モードの場合はツールなしで直接モデルで処理
        if self.connection_mode == ConnectionMode.SIMPLE:
            if self.model_provider == "anthropic":
                # 簡易モードでのAnthropicの処理（LangChain経由）
                result = await self.anthropic_handler.process_query_simple(query)
                # 応答を会話履歴に追加
                self.conversation_history.append(AIMessage(content=result))
                return result
            else:
                # 簡易モードでのGeminiの処理（LangChain経由）
                result = await self.gemini_handler.process_query_simple(query)
                # 応答を会話履歴に追加
                self.conversation_history.append(AIMessage(content=result))
                return result

        # 完全モードでの処理 (MCPサーバー接続)
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
            result = await self._process_cross_server_query(query, thread_ts, user_id)
            # 応答を会話履歴に追加
            self.conversation_history.append(AIMessage(content=result))
            return result
        elif self.model_provider == "anthropic":
            # Process with Anthropic (Claude) using LangChain
            async def tool_executor(tool_name, tool_args):
                return await self.tool_manager.execute_tool(tool_name, tool_args)

            # LangChain経由でAnthropicの処理
            result = await self.anthropic_handler.process_query(
                query, tools, tool_executor
            )

            # 応答を会話履歴に追加
            self.conversation_history.append(AIMessage(content=result))

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.session_manager.current_server == "slack":
                await self.slack_service.reply_to_slack_thread(
                    result, thread_ts, user_id
                )

            return result
        else:
            # Process with Gemini using LangChain
            async def tool_executor(tool_name, tool_args):
                return await self.tool_manager.execute_tool(tool_name, tool_args)

            # LangChain経由でGeminiの処理
            result = await self.gemini_handler.process_query(
                query, tools, tool_executor, self.session_manager.default_channel_id
            )

            # 応答を会話履歴に追加
            self.conversation_history.append(AIMessage(content=result))

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.session_manager.current_server == "slack":
                await self.slack_service.reply_to_slack_thread(
                    result, thread_ts, user_id
                )

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
                    await self.connect_to_server(server_name="notion")
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
        print(f"Connection mode: {self.connection_mode.value}")
        print(f"Operation mode: {self.operation_mode.value}")

        # 簡易モードの場合は追加の情報を表示
        if self.connection_mode == ConnectionMode.SIMPLE:
            print("Running in SIMPLE mode - direct model access without MCP tools")
        else:
            print("Running in FULL mode - connected to MCP server with tools")
            if self.session_manager.current_server:
                print(f"Connected to server: {self.session_manager.current_server}")

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
        # LangGraphリソースのクリーンアップ
        if self.graph_manager:
            await self.graph_manager.cleanup()

        # セッションのクリーンアップ
        await self.session_manager.cleanup()

        # サービスのリセット
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
    connection_group = parser.add_argument_group("Connection Options")
    server_group = connection_group.add_mutually_exclusive_group()
    server_group.add_argument(
        "--server", "-s", help="Server name from schema (e.g., slack)"
    )
    server_group.add_argument("--path", "-p", help="Path to server script file")

    parser.add_argument(
        "--mode",
        choices=["simple", "full"],
        default="full",
        help="Connection mode: 'simple' for direct script execution or 'full' for MCP server connection (default: full)",
    )
    parser.add_argument(
        "--operation",
        choices=["langchain", "langgraph"],
        default="langgraph",
        help="Operation mode: 'langchain' for single agent or 'langgraph' for multi-agent (default: langgraph)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default="anthropic",
        choices=["gemini", "anthropic"],
        help="Model provider to use (default: anthropic)",
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

    # 接続モードの設定
    connection_mode = (
        ConnectionMode.SIMPLE if args.mode == "simple" else ConnectionMode.FULL
    )

    # 操作モードの設定
    operation_mode = (
        OperationMode.LANGCHAIN
        if args.operation == "langchain"
        else OperationMode.LANGGRAPH
    )

    # サーバー名またはパスが指定されていない場合、必要に応じて要求
    if connection_mode == ConnectionMode.FULL and not (args.server or args.path):
        parser.error("Full connection mode requires --server or --path")

    client = MCPClient(
        model_provider=args.model,
        connection_mode=connection_mode,
        operation_mode=operation_mode,
    )

    try:
        # データベース機能の初期化
        await client.initialize_database()

        # 接続モードに応じてサーバー接続（完全モードのみ）
        if connection_mode == ConnectionMode.FULL:
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
