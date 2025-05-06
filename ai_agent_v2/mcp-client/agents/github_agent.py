"""
GitHubリサーチエージェントモジュール

GitHubリポジトリのコードを検索・分析し、問題を発見するためのエージェントを提供します
LangGraphフレームワークに対応
"""

import logging
import re
from typing import Any, Dict, List, Optional

from config import get_agent_prompts
from core.utils import analyze_code_issues
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tools.handlers import ToolManager

logger = logging.getLogger(__name__)


class GitHubResearchAgent:
    """
    GitHubリサーチエージェント

    GitHubリポジトリのコードを検索し、潜在的な問題を分析します。
    LangGraphのエージェントノードとして機能します。
    """

    def __init__(
        self,
        llm: Optional[ChatAnthropic] = None,
        tool_manager: Optional[ToolManager] = None,
    ):
        """
        GitHubResearchAgentの初期化

        Args:
            llm: 言語モデル
            tool_manager: MCPツール管理のインスタンス
        """
        self.llm = llm
        self.tool_manager = tool_manager
        self.prompts = get_agent_prompts()

    async def _extract_search_terms(self, query: str) -> List[str]:
        """
        クエリから検索語を抽出

        Args:
            query: ユーザーからのクエリ文字列

        Returns:
            List[str]: 抽出された検索語のリスト
        """
        # 引用符で囲まれたフレーズを抽出
        quote_pattern = r'"([^"]+)"'
        quoted_terms = re.findall(quote_pattern, query)

        if quoted_terms:
            return quoted_terms

        # LLMを使用して検索語を推測
        github_prompt = self.prompts.get("github_research", "")
        messages = [
            SystemMessage(content=github_prompt),
            HumanMessage(
                content=f"次のユーザークエリから、コード検索に使用すべき重要なキーワードを最大3つ抽出してください。キーワードのみをカンマ区切りのリストとして返してください。\n\nクエリ: {query}"
            ),
        ]

        response = await self.llm.ainvoke(messages)
        response_text = response.content.strip()

        # カンマ区切りの応答をリストに変換
        terms = [term.strip() for term in response_text.split(",") if term.strip()]

        # 汎用的すぎる語や短すぎる語（3文字未満）を除外
        filtered_terms = [
            term
            for term in terms
            if len(term) >= 3
            and term.lower()
            not in [
                "code",
                "github",
                "バグ",
                "エラー",
                "問題",
                "issue",
                "bug",
                "error",
                "problem",
            ]
        ]

        return filtered_terms[:3] if filtered_terms else ["error", "bug", "TODO"]

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        クエリを処理してGitHub情報を返す

        LangGraphのノード関数として機能し、状態を更新します。

        Args:
            state: 現在の状態

        Returns:
            Dict[str, Any]: 更新された状態
        """
        query = state.get("query", "")
        query_type = state.get("query_type", "")

        try:
            if not self.tool_manager:
                raise ValueError("ToolManagerが初期化されていません")

            # ツールの利用可能性を確認
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            github_info = []
            search_results = {}
            code_analyses = []

            # 検索語を抽出
            search_terms = await self._extract_search_terms(query)

            # リポジトリ情報の取得
            if "github_list_repos" in tool_names:
                repos_info = await self.tool_manager.execute_tool(
                    "github_list_repos", {}
                )
                github_info.append(f"リポジトリ一覧:\n{repos_info}")

            # コード検索の実行
            if "github_search_code" in tool_names and search_terms:
                for term in search_terms:
                    search_result = await self.tool_manager.execute_tool(
                        "github_search_code", {"query": term}
                    )
                    search_results[term] = search_result
                    github_info.append(f"「{term}」のコード検索結果:\n{search_result}")

                    # コードファイルの分析
                    if search_result and "github_get_content" in tool_names:
                        # ファイルパスを抽出
                        file_paths = re.findall(
                            r"([a-zA-Z0-9_\-/\.]+\.(py|js|ts|go|java|rb))",
                            search_result,
                        )

                        if file_paths:
                            # 最初のファイルを取得
                            file_path = file_paths[0][0]
                            repo_match = re.search(
                                r"([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+):", search_result
                            )

                            if repo_match:
                                repo_name = repo_match.group(1)
                                content_result = await self.tool_manager.execute_tool(
                                    "github_get_content",
                                    {"repo": repo_name, "path": file_path},
                                )

                                # コード分析の実行
                                analysis = analyze_code_issues(content_result, term)
                                code_analyses.append(
                                    {
                                        "file": file_path,
                                        "repo": repo_name,
                                        "analysis": analysis,
                                    }
                                )
                                github_info.append(
                                    f"ファイル「{file_path}」の問題分析:\n{analysis}"
                                )

            # 未解決の問題を取得
            if "github_list_issues" in tool_names and (
                "問題" in query or "issue" in query.lower() or "バグ" in query
            ):
                issues_info = await self.tool_manager.execute_tool(
                    "github_list_issues", {"state": "open"}
                )
                github_info.append(f"未解決の問題一覧:\n{issues_info}")

            # 情報が取得できなかった場合のフォールバック
            if not github_info:
                if "github_list_repos" in tool_names:
                    repos_info = await self.tool_manager.execute_tool(
                        "github_list_repos", {}
                    )
                    github_info.append(f"リポジトリ一覧:\n{repos_info}")

            # LLMを使用して結果を分析・整理
            github_prompt = self.prompts.get("github_research", "")
            combined_info = "\n\n".join(github_info)

            messages = [
                SystemMessage(content=github_prompt),
                HumanMessage(
                    content=f"次のGitHubリポジトリ情報を分析し、技術的問題点をまとめてください。\n\nユーザークエリ: {query}\n\n取得情報:\n{combined_info}"
                ),
            ]

            analysis_response = await self.llm.ainvoke(messages)
            analysis_text = analysis_response.content

            # 結果をフォーマット
            github_result = {
                "query": query,
                "search_terms": search_terms,
                "raw_info": github_info,
                "code_analyses": code_analyses,
                "summary": analysis_text,
            }

            # Notionタスク作成が必要かどうかを評価
            needs_task = query_type == "task_creation" or (
                any(
                    "問題" in analysis
                    for _, _, analysis in [
                        (a.get("file"), a.get("repo"), a.get("analysis"))
                        for a in code_analyses
                    ]
                )
                and any(
                    term in analysis_text.lower()
                    for term in [
                        "修正",
                        "対応",
                        "改善",
                        "必要",
                        "should",
                        "must",
                        "fix",
                        "improve",
                    ]
                )
            )

            # 状態を更新
            state_update = {"github_result": github_result, "response": analysis_text}

            # タスク作成が必要なら、状態に反映
            if needs_task and query_type != "task_creation":
                state_update["query_type"] = "task_creation"

            return state_update

        except Exception as e:
            logger.error(f"GitHubリサーチエージェント処理エラー: {str(e)}")

            # エラー時の状態更新
            return {
                "github_result": {"error": str(e)},
                "response": f"GitHub情報の取得・分析中にエラーが発生しました: {str(e)}",
            }
