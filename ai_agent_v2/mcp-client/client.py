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
        response = await self.session.list_tools()

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
            # Format for Anthropic (Claude)
            result = await self._process_with_anthropic(query, response.tools)

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.current_server == "slack":
                await self._reply_to_slack_thread(result, thread_ts, user_id)

            return result
        else:
            # Format for Gemini
            result = await self._process_with_gemini(query, response.tools)

            # If we have thread_ts and user_id, it's a Slack message we should reply to
            if thread_ts and user_id and self.current_server == "slack":
                await self._reply_to_slack_thread(result, thread_ts, user_id)

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

                # Step 2: Get GitHub information & analyze code issues
                github_info = await self._extract_github_info(query)
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
                    notion_task_info = await self._create_notion_task(
                        github_info, query
                    )
                    result_text.append(f"Notionタスク作成結果: {notion_task_info}")

                # Step 4: Reconnect to Slack to post the summary
                await self.cleanup()  # Close current connection
                result_text.append("Slackサーバーに接続中...")
                await self.connect_to_server(server_name="slack")
                result_text.append("Slack接続成功")

                # Step 5: Post to Slack with combined info
                if self.default_channel_id:
                    # Prepare summary message including GitHub findings and Notion task if created
                    summary = f"GitHubコード分析結果:\n{github_info}"
                    if notion_task_info:
                        summary += f"\n\nNotionタスク作成:\n{notion_task_info}"

                    # If we have thread info, reply to thread
                    if thread_ts and user_id:
                        post_result = await self._reply_to_slack_thread(
                            summary, thread_ts, user_id
                        )
                        result_text.append(f"Slackスレッドへの返信結果: {post_result}")
                    else:
                        # Otherwise post as a new message
                        post_result = await self._post_to_slack(summary)
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
                elif original_server == "notionApi":
                    await self.connect_to_server(server_name="notionApi")

            return "\n".join(result_text)
        except Exception as e:
            return f"サーバー間操作中にエラーが発生しました: {str(e)}"

    async def _extract_github_info(self, query: str) -> str:
        """
        GitHubからクエリに基づいて情報を抽出し、問題コードを分析

        このメソッドは、GitHub MCPサーバーを介してGitHubから情報を取得します。
        コード検索、リポジトリ分析、問題のあるコードの特定などを行います。

        クエリ内容を分析し、適切なGithubツールを使用してコードや問題を検索します。
        検索したコードに問題が見つかった場合は、その問題内容も分析します。

        Args:
            query: 情報抽出のためのクエリ

        Returns:
            str: GitHubから取得した情報と問題分析結果
        """
        try:
            # Check available GitHub tools
            response = await self.session.list_tools()
            tools = [tool.name for tool in response.tools]

            results = []

            # Parse query to identify what to search for
            query_lower = query.lower()

            # Repository related searches
            if (
                "リポジトリ" in query
                or "レポジトリ" in query
                or "repository" in query_lower
            ):
                if "github_list_repos" in tools:
                    result = await self.session.call_tool("github_list_repos", {})
                    repos_info = self._extract_tool_content(result.content)
                    results.append(f"リポジトリ一覧:\n{repos_info}")

            # Code search related
            code_search_terms = []
            if "コード検索" in query or "code search" in query_lower:
                # Extract potential search terms from the query
                # Look for terms in quotes or specific keywords
                import re

                quote_pattern = r'"([^"]+)"'
                quoted_terms = re.findall(quote_pattern, query)

                if quoted_terms:
                    code_search_terms.extend(quoted_terms)
                else:
                    # Try to extract key terms
                    potential_terms = [
                        term
                        for term in query.split()
                        if len(term) > 3
                        and term
                        not in ["コード検索", "検索", "github", "code", "search"]
                    ]
                    if potential_terms:
                        code_search_terms.extend(
                            potential_terms[:2]
                        )  # Use first 2 longer terms

            # Perform code search if we have terms
            if code_search_terms and "github_search_code" in tools:
                for term in code_search_terms:
                    result = await self.session.call_tool(
                        "github_search_code", {"query": term}
                    )
                    search_results = self._extract_tool_content(result.content)
                    results.append(f"「{term}」のコード検索結果:\n{search_results}")

                    # If we find code, analyze it for potential issues
                    if (
                        search_results
                        and len(search_results) > 10
                        and "github_get_content" in tools
                    ):
                        # Extract a file path from the search results
                        import re

                        file_paths = re.findall(
                            r"([a-zA-Z0-9_\-/\.]+\.(py|js|ts|go|java|rb))",
                            search_results,
                        )

                        if file_paths:
                            # Get the first file content
                            file_path = file_paths[0][0]
                            repo_name = None

                            # Try to extract repo name from search results
                            repo_match = re.search(
                                r"([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+):",
                                search_results,
                            )
                            if repo_match:
                                repo_name = repo_match.group(1)

                            if repo_name:
                                content_result = await self.session.call_tool(
                                    "github_get_content",
                                    {"repo": repo_name, "path": file_path},
                                )
                                file_content = self._extract_tool_content(
                                    content_result.content
                                )

                                # Analyze code for potential issues
                                analysis = self._analyze_code_issues(file_content, term)
                                if analysis:
                                    results.append(
                                        f"ファイル「{file_path}」の問題分析:\n{analysis}"
                                    )

            # Issue related searches
            if "問題" in query or "issue" in query_lower or "バグ" in query:
                if "github_list_issues" in tools:
                    result = await self.session.call_tool(
                        "github_list_issues", {"state": "open"}
                    )
                    issues_info = self._extract_tool_content(result.content)
                    results.append(f"未解決の問題一覧:\n{issues_info}")

            # If no specific search was performed, fallback to general repo info
            if not results:
                if "github_list_repos" in tools:
                    result = await self.session.call_tool("github_list_repos", {})
                    return self._extract_tool_content(result.content)
                elif "github_get_user" in tools:
                    result = await self.session.call_tool("github_get_user", {})
                    return self._extract_tool_content(result.content)
                else:
                    return "利用可能なGitHubツールが見つかりませんでした"

            return "\n\n".join(results)
        except Exception as e:
            return f"GitHub情報取得エラー: {str(e)}"

    def _analyze_code_issues(self, code_content: str, search_term: str) -> str:
        """
        コードの問題点を分析

        このメソッドは、取得したコード内容を分析して潜在的な問題点を特定します。
        単純なルールベースの分析を行い、コードの質や潜在的なバグを検出します。

        Args:
            code_content: 分析するコードコンテンツ
            search_term: 検索に使用した用語

        Returns:
            str: 検出された問題点の説明
        """
        issues = []

        # 明らかなコードの問題を検出
        if "TODO" in code_content:
            issues.append("未完了の TODO コメントが含まれています")

        if "FIXME" in code_content:
            issues.append("修正が必要な FIXME コメントが含まれています")

        if "BUG" in code_content or "bug" in code_content.lower():
            issues.append("バグに関する言及があります")

        # セキュリティ関連の問題
        if any(
            term in code_content.lower()
            for term in ["password", "secret", "key", "token", "パスワード", "秘密"]
        ):
            if any(
                term in code_content.lower() for term in ["hardcoded", "ハードコード"]
            ):
                issues.append(
                    "ハードコードされた機密情報が含まれている可能性があります"
                )

        # エラーハンドリング
        if (
            "try" in code_content.lower()
            and "except" not in code_content.lower()
            and "catch" not in code_content.lower()
        ):
            issues.append("エラーハンドリングが不完全な可能性があります")

        # 検索語に基づく分析
        if search_term.lower() in code_content.lower():
            lines_with_term = [
                line.strip()
                for line in code_content.split("\n")
                if search_term.lower() in line.lower()
            ]
            if lines_with_term:
                term_context = "\n".join(lines_with_term[:3])  # 最初の3行まで
                issues.append(f"検索語「{search_term}」を含む箇所:\n{term_context}")

        # パフォーマンスの問題
        if (
            "for" in code_content.lower()
            and "for" in code_content.lower().split("for")[1]
        ):
            issues.append(
                "ネストされたループがあり、パフォーマンスの問題がある可能性があります"
            )

        # 結果を返す
        if issues:
            return "- " + "\n- ".join(issues)
        else:
            return "明らかな問題は検出されませんでした"

    async def _create_notion_task(self, github_info: str, original_query: str) -> str:
        """
        Notionにタスクを作成

        このメソッドは、Notion MCPサーバーを介してNotionデータベースに
        タスクを作成します。GitHub検索結果に基づいて問題点を特定し、
        修正タスクをNotionに登録します。

        Args:
            github_info: GitHubから取得した情報
            original_query: 元のユーザークエリ

        Returns:
            str: タスク作成結果のメッセージ
        """
        try:
            # Check available Notion tools
            response = await self.session.list_tools()
            tools = [tool.name for tool in response.tools]

            if "notion_create_page" not in tools:
                return "Notionページ作成ツールが利用できません"

            # Extract key information from GitHub info to create a meaningful task
            # Look for code issues or problems mentioned in the GitHub info
            task_title = "コード修正タスク"
            issue_summary = []
            code_file = None

            # Extract file paths mentioned
            import re

            file_paths = re.findall(r"ファイル「([^」]+)」", github_info)
            if file_paths:
                code_file = file_paths[0]
                task_title = f"{code_file} の修正"

            # Extract issues
            issues_section = None
            if "問題分析" in github_info:
                analysis_parts = github_info.split("問題分析:")
                if len(analysis_parts) > 1:
                    issues_section = analysis_parts[1].strip()

            if issues_section:
                # Extract bullet points
                issue_lines = [
                    line.strip()
                    for line in issues_section.split("\n")
                    if line.strip().startswith("-")
                ]
                issue_summary = [line[2:].strip() for line in issue_lines]

            # Create task description
            task_description = f"""
## 修正タスク

### 元のクエリ
{original_query}

### 対象ファイル
{code_file if code_file else "特定のファイルは指定されていません"}

### 検出された問題点
{"- " + "\n- ".join(issue_summary) if issue_summary else "詳細な問題点は検出されませんでした"}

### GitHub情報
```
{github_info[:500]}{"..." if len(github_info) > 500 else ""}
```

### 修正手順
1. 該当コードを確認する
2. 問題点を理解する
3. 修正案を検討する
4. 修正を実装する
5. テストを実施する
6. プルリクエストを作成する
            """

            # Look for appropriate Notion database ID
            # First try to see if we can list databases
            database_id = None
            if "notion_list_databases" in tools:
                result = await self.session.call_tool("notion_list_databases", {})
                databases_info = self._extract_tool_content(result.content)

                # Try to find a Tasks or Projects database
                import json

                try:
                    if isinstance(
                        databases_info, str
                    ) and databases_info.strip().startswith("{"):
                        databases = json.loads(databases_info)
                        for db in databases.get("results", []):
                            db_title = db.get("title", "").lower()
                            if (
                                "task" in db_title
                                or "project" in db_title
                                or "todo" in db_title
                            ):
                                database_id = db.get("id")
                                break
                except (json.JSONDecodeError, AttributeError):
                    pass

            # If we couldn't find a database ID, use a default task database ID if available
            if not database_id:
                # Default database ID might be set in the future or obtained from environment
                # For now, we'll return an error if we can't find one
                return "タスク用のNotionデータベースが見つかりませんでした"

            # Create the task in Notion
            properties = {
                "Name": {"title": [{"text": {"content": task_title}}]},
                "Status": {"select": {"name": "未着手"}},
                "Priority": {"select": {"name": "中"}},
            }

            # Add a due date about a week from now
            from datetime import datetime, timedelta

            due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            properties["Due"] = {"date": {"start": due_date}}

            # Create the page
            result = await self.session.call_tool(
                "notion_create_page",
                {
                    "database_id": database_id,
                    "properties": properties,
                    "content": task_description,
                },
            )

            response_content = self._extract_tool_content(result.content)

            # Extract page URL for easy access
            page_url = None
            try:
                response_data = (
                    json.loads(response_content)
                    if isinstance(response_content, str)
                    else response_content
                )
                page_url = response_data.get("url")
            except (json.JSONDecodeError, AttributeError):
                page_url = "URL取得できませんでした"

            return f"Notionタスク「{task_title}」が作成されました。\nURL: {page_url}"

        except Exception as e:
            return f"Notionタスク作成エラー: {str(e)}"

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

            # Check if the content is too long and summarize if needed
            if len(content) > 2000:
                message = f"要約された情報:\n```\n{content[:1000]}...\n\n...(長いため省略されました。全部で{len(content)}文字)...\n```"
            else:
                message = f"取得した情報:\n```\n{content}\n```"

            result = await self.session.call_tool(
                "slack_post_message",
                {"channel_id": self.default_channel_id, "text": message},
            )

            return self._extract_tool_content(result.content)
        except Exception as e:
            return f"Slack投稿エラー: {str(e)}"

    async def _reply_to_slack_thread(
        self, content: str, thread_ts: str, user_id: str
    ) -> str:
        """
        Slackスレッドに返信

        このメソッドは、特定のSlackスレッドにメンション付きで返信します。
        長い内容の場合は自動的に要約を行います。

        Args:
            content: 返信内容
            thread_ts: 返信先スレッドのタイムスタンプ
            user_id: メンション先のユーザーID

        Returns:
            str: 返信結果のメッセージ
        """
        try:
            if not self.default_channel_id:
                return "デフォルトのSlackチャンネルIDが設定されていません"

            # Format message with mention
            user_mention = f"<@{user_id}>"

            # Check if the content is too long and summarize
            if len(content) > 2000:
                # Split into paragraphs
                paragraphs = content.split("\n\n")

                # Take the first paragraph and some key information
                summary_parts = [paragraphs[0]]

                # Look for important sections like "問題分析" or "Notionタスク作成"
                important_sections = []
                for para in paragraphs:
                    if any(
                        keyword in para
                        for keyword in ["問題分析", "Notionタスク", "URL:", "修正手順"]
                    ):
                        important_sections.append(para)

                # Add up to 3 important sections
                summary_parts.extend(important_sections[:3])

                # Create summarized message
                summarized_content = "\n\n".join(summary_parts)
                message = f"{user_mention} 結果の要約です:\n\n{summarized_content}\n\n(詳細は省略されました。全部で{len(content)}文字)"
            else:
                message = f"{user_mention}\n\n{content}"

            # Check if thread_reply tool is available
            response = await self.session.list_tools()
            tools = [tool.name for tool in response.tools]

            if "slack_reply_to_thread" in tools:
                result = await self.session.call_tool(
                    "slack_reply_to_thread",
                    {
                        "channel_id": self.default_channel_id,
                        "text": message,
                        "thread_ts": thread_ts,
                    },
                )
                return self._extract_tool_content(result.content)
            else:
                # Fallback to regular post with thread_ts
                result = await self.session.call_tool(
                    "slack_post_message",
                    {
                        "channel_id": self.default_channel_id,
                        "text": message,
                        "thread_ts": thread_ts,
                    },
                )
                return self._extract_tool_content(result.content)

        except Exception as e:
            return f"Slackスレッド返信エラー: {str(e)}"

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
        await self.exit_stack.aclose()


async def main():
    """
    メインの実行関数

    コマンドライン引数を解析し、適切なモデルとサーバーでMCPクライアントを起動します。
    スレッド情報やユーザーIDも指定可能で、Slackの自動化スクリプトからも呼び出せます。

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
