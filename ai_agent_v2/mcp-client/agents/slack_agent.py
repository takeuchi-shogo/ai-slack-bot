"""
Slack応答エージェントモジュール

処理結果をSlackチャンネルやスレッドに返信するエージェントを提供します
LangGraphフレームワークに対応
"""

import logging
from typing import Any, Dict, Optional

from config import get_agent_prompts
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tools.handlers import ToolManager

logger = logging.getLogger(__name__)


class SlackResponseAgent:
    """
    Slack応答エージェント

    処理結果を整形し、Slackに返信します。
    LangGraphのエージェントノードとして機能します。
    """

    def __init__(
        self,
        llm: Optional[ChatAnthropic] = None,
        tool_manager: Optional[ToolManager] = None,
    ):
        """
        SlackResponseAgentの初期化

        Args:
            llm: 言語モデル
            tool_manager: MCPツール管理のインスタンス
        """
        self.llm = llm
        self.tool_manager = tool_manager
        self.prompts = get_agent_prompts()

    async def _summarize_content(self, content: str, max_length: int = 2000) -> str:
        """
        長い内容を要約

        Args:
            content: 要約する内容
            max_length: 最大文字数

        Returns:
            str: 要約された内容
        """
        if len(content) <= max_length:
            return content

        # 段落に分割
        paragraphs = content.split("\n\n")

        # 最初の段落と重要な部分を抽出
        summary_parts = [paragraphs[0]]

        # 重要なセクションを探す
        important_sections = []
        for para in paragraphs:
            if any(
                keyword in para
                for keyword in [
                    "問題分析",
                    "Notionタスク",
                    "URL:",
                    "修正手順",
                    "データベース",
                    "結果",
                    "結論",
                    "まとめ",
                ]
            ):
                important_sections.append(para)

        # 重要なセクションを最大3つまで追加
        summary_parts.extend(important_sections[:3])

        # 要約を作成
        summarized_content = "\n\n".join(summary_parts)

        # それでも長い場合はLLMで要約
        if len(summarized_content) > max_length:
            slack_prompt = self.prompts.get("slack_response", "")
            messages = [
                SystemMessage(content=slack_prompt),
                HumanMessage(
                    content=f"次の文章を{max_length}文字以内に要約してください。重要なポイントを保持し、専門用語をわかりやすく説明してください。\n\n{content}"
                ),
            ]

            response = await self.llm.ainvoke(messages)
            summarized_content = response.content

            # 最大長さを超えた場合は切り詰め
            if len(summarized_content) > max_length:
                summarized_content = (
                    summarized_content[: max_length - 100]
                    + f"\n\n...(省略されました。全{len(content)}文字)"
                )

        return summarized_content

    async def _format_response(self, state: Dict[str, Any]) -> str:
        """
        状態から応答を整形

        Args:
            state: 現在の状態

        Returns:
            str: 整形された応答
        """
        query = state.get("query", "")
        query_type = state.get("query_type", "")
        db_result = state.get("db_result", {})
        github_result = state.get("github_result", {})
        notion_result = state.get("notion_result", {})
        response = state.get("response", "")

        # すでに整形された応答がある場合はそれを使用
        if response:
            return response

        # LLMで応答を生成
        slack_prompt = self.prompts.get("slack_response", "")

        # 情報を整理
        context_info = [f"ユーザークエリ: {query}", f"クエリタイプ: {query_type}"]

        if db_result:
            db_explanation = db_result.get("explanation", "")
            if db_explanation:
                context_info.append(f"データベース結果: {db_explanation[:500]}...")

        if github_result:
            github_summary = github_result.get("summary", "")
            if github_summary:
                context_info.append(f"GitHub分析: {github_summary[:500]}...")

        if notion_result:
            task_title = notion_result.get("task_title", "")
            page_url = notion_result.get("page_url", "")
            if task_title and page_url:
                context_info.append(f"Notionタスク: {task_title} (URL: {page_url})")

        # LLMで応答を生成
        messages = [
            SystemMessage(content=slack_prompt),
            HumanMessage(
                content=f"次の情報を基に、非技術者にもわかりやすい応答を作成してください。重要なポイントを簡潔にまとめ、専門用語は平易な言葉で説明してください。\n\n{' '.join(context_info)}"
            ),
        ]

        response = await self.llm.ainvoke(messages)
        return response.content

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        状態を処理して最終応答を作成・送信

        LangGraphのノード関数として機能し、状態を更新します。

        Args:
            state: 現在の状態

        Returns:
            Dict[str, Any]: 更新された状態
        """
        try:
            # 応答を整形
            formatted_response = await self._format_response(state)

            # 長さを確認して必要なら要約
            final_response = await self._summarize_content(formatted_response)

            # スレッド情報とユーザーIDを取得
            thread_ts = state.get("thread_ts")
            user_id = state.get("user_id")

            # Slackに送信
            if self.tool_manager and thread_ts and user_id:
                tools = await self.tool_manager.list_available_tools()
                tool_names = [tool.name for tool in tools]

                # ユーザーメンションを追加
                user_mention = f"<@{user_id}>"
                message = f"{user_mention}\n\n{final_response}"

                # スレッド返信ツールがあれば使用
                if "slack_reply_to_thread" in tool_names:
                    await self.tool_manager.execute_tool(
                        "slack_reply_to_thread",
                        {
                            "text": message,
                            "thread_ts": thread_ts,
                        },
                    )
                elif "slack_post_message" in tool_names:
                    # フォールバックとして通常の投稿ツールでスレッドに返信
                    await self.tool_manager.execute_tool(
                        "slack_post_message",
                        {
                            "text": message,
                            "thread_ts": thread_ts,
                        },
                    )

            # 状態を更新
            return {"response": final_response}

        except Exception as e:
            logger.error(f"Slack応答エージェント処理エラー: {str(e)}")

            # エラー時の状態更新
            return {"response": f"応答の処理中にエラーが発生しました: {str(e)}"}
