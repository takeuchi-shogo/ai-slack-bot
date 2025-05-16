import json
import logging
from typing import Any, Dict

from config import GITHUB_RESEARCH_SYSTEM_PROMPT
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from models.anthropic import AnthropicModelHandler

load_dotenv()
logger = logging.getLogger(__name__)


class GithubAgent:
    """GitHub関連のクエリを処理するエージェント"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()
        self.mcp_config = None

        try:
            with open("mcp_config/github.json", "r") as f:
                self.mcp_config = json.load(f)
        except FileNotFoundError:
            logger.error("GitHub MCP設定ファイルが見つかりません")
            raise

    async def simple_chat(self, message: str) -> Dict[str, Any]:
        """GitHubに関する基本的なクエリを処理する

        Args:
            message: ユーザーからのメッセージ

        Returns:
            エージェントの応答
        """
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            tools = client.get_tools()

            # ReActエージェントの作成
            agent = create_react_agent(
                self.model_handler.llm,
                tools,
            )

            # システムメッセージをメッセージリストに追加
            agent_response = await agent.ainvoke(
                {
                    "messages": [
                        {"role": "system", "content": GITHUB_RESEARCH_SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                }
            )

            return agent_response

    async def search_repositories(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """GitHubリポジトリを検索する

        Args:
            query: 検索クエリ
            limit: 検索結果の最大数

        Returns:
            検索結果
        """
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            # GitHubツールを取得
            github_tools = [
                tool for tool in client.get_tools() if "github" in tool.name.lower()
            ]

            # リポジトリ検索ツールを特定
            search_tool = next(
                (
                    tool
                    for tool in github_tools
                    if "search" in tool.name.lower()
                    and "repositories" in tool.name.lower()
                ),
                None,
            )

            if not search_tool:
                logger.error("GitHub検索ツールが見つかりません")
                return {"error": "GitHub検索ツールが見つかりません"}

            # 検索パラメータを準備
            params = {"q": query, "per_page": limit}

            # 検索を実行
            result = await client.ainvoke_tool(search_tool, params)
            return result

    async def get_repository_content(
        self, repo_owner: str, repo_name: str, path: str = ""
    ) -> Dict[str, Any]:
        """GitHubリポジトリのコンテンツを取得する

        Args:
            repo_owner: リポジトリ所有者名
            repo_name: リポジトリ名
            path: 取得するファイルやディレクトリのパス（空の場合はルート）

        Returns:
            コンテンツ情報
        """
        async with MultiServerMCPClient(self.mcp_config["mcpServers"]) as client:
            # GitHubツールを取得
            github_tools = [
                tool for tool in client.get_tools() if "github" in tool.name.lower()
            ]

            # コンテンツ取得ツールを特定
            content_tool = next(
                (tool for tool in github_tools if "contents" in tool.name.lower()), None
            )

            if not content_tool:
                logger.error("GitHubコンテンツツールが見つかりません")
                return {"error": "GitHubコンテンツツールが見つかりません"}

            # パラメータを準備
            params = {"owner": repo_owner, "repo": repo_name, "path": path}

            # コンテンツを取得
            result = await client.ainvoke_tool(content_tool, params)
            return result

    async def analyze_repository(
        self, repo_owner: str, repo_name: str
    ) -> Dict[str, Any]:
        """GitHubリポジトリの概要分析を行う

        Args:
            repo_owner: リポジトリ所有者名
            repo_name: リポジトリ名

        Returns:
            分析結果
        """
        # READMEを取得
        readme_content = await self.get_repository_content(
            repo_owner, repo_name, "README.md"
        )

        # リポジトリ構造を取得
        structure = await self.get_repository_content(repo_owner, repo_name)

        # 分析プロンプトを作成
        prompt = f"""
        次のGitHubリポジトリの分析を行ってください：
        
        リポジトリ: {repo_owner}/{repo_name}
        
        README内容:
        {readme_content.get("content", "README情報なし")}
        
        リポジトリ構造:
        {structure}
        
        以下の点について簡潔に分析してください：
        1. リポジトリの主な目的
        2. 使用されている主要な技術
        3. プロジェクトの構造
        4. 注目すべき特徴
        """

        # 分析実行
        response = await self.model_handler.llm.ainvoke(
            [{"content": prompt, "role": "user"}]
        )

        return {"repo": f"{repo_owner}/{repo_name}", "analysis": response.content}
