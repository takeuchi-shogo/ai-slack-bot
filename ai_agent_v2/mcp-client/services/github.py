"""
GitHub サービスモジュール

GitHub APIとの連携機能を提供します
"""

import re

from ..core.utils import analyze_code_issues


class GitHubService:
    """
    GitHubサービスを管理するクラス
    """

    def __init__(self, tool_manager):
        """
        GitHubServiceの初期化

        Args:
            tool_manager: ツール管理インスタンス
        """
        self.tool_manager = tool_manager

    async def extract_github_info(self, query: str) -> str:
        """
        GitHubからクエリに基づいて情報を抽出し、問題コードを分析

        Args:
            query: 情報抽出のためのクエリ

        Returns:
            str: GitHubから取得した情報と問題分析結果
        """
        try:
            # Check available GitHub tools
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            results = []

            # Parse query to identify what to search for
            query_lower = query.lower()

            # Repository related searches
            if (
                "リポジトリ" in query
                or "レポジトリ" in query
                or "repository" in query_lower
            ):
                if "github_list_repos" in tool_names:
                    result = await self.tool_manager.execute_tool(
                        "github_list_repos", {}
                    )
                    repos_info = result
                    results.append(f"リポジトリ一覧:\n{repos_info}")

            # Code search related
            code_search_terms = []
            if "コード検索" in query or "code search" in query_lower:
                # Extract potential search terms from the query
                # Look for terms in quotes or specific keywords
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
            if code_search_terms and "github_search_code" in tool_names:
                for term in code_search_terms:
                    result = await self.tool_manager.execute_tool(
                        "github_search_code", {"query": term}
                    )
                    search_results = result
                    results.append(f"「{term}」のコード検索結果:\n{search_results}")

                    # If we find code, analyze it for potential issues
                    if (
                        search_results
                        and len(search_results) > 10
                        and "github_get_content" in tool_names
                    ):
                        # Extract a file path from the search results
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
                                content_result = await self.tool_manager.execute_tool(
                                    "github_get_content",
                                    {"repo": repo_name, "path": file_path},
                                )
                                file_content = content_result

                                # Analyze code for potential issues
                                analysis = analyze_code_issues(file_content, term)
                                if analysis:
                                    results.append(
                                        f"ファイル「{file_path}」の問題分析:\n{analysis}"
                                    )

            # Issue related searches
            if "問題" in query or "issue" in query_lower or "バグ" in query:
                if "github_list_issues" in tool_names:
                    result = await self.tool_manager.execute_tool(
                        "github_list_issues", {"state": "open"}
                    )
                    issues_info = result
                    results.append(f"未解決の問題一覧:\n{issues_info}")

            # If no specific search was performed, fallback to general repo info
            if not results:
                if "github_list_repos" in tool_names:
                    result = await self.tool_manager.execute_tool(
                        "github_list_repos", {}
                    )
                    return result
                elif "github_get_user" in tool_names:
                    result = await self.tool_manager.execute_tool("github_get_user", {})
                    return result
                else:
                    return "利用可能なGitHubツールが見つかりませんでした"

            return "\n\n".join(results)
        except Exception as e:
            return f"GitHub情報取得エラー: {str(e)}"
