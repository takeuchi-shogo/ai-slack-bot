"""
Slack サービスモジュール

Slack APIとの連携機能を提供します
"""


class SlackService:
    """
    Slackサービスを管理するクラス
    """

    def __init__(self, tool_manager, default_channel_id=None):
        """
        SlackServiceの初期化

        Args:
            tool_manager: ツール管理インスタンス
            default_channel_id: デフォルトのSlackチャンネルID
        """
        self.tool_manager = tool_manager
        self.default_channel_id = default_channel_id

    async def post_to_slack(self, content: str) -> str:
        """
        Slackチャンネルに内容を投稿

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

            result = await self.tool_manager.execute_tool(
                "slack_post_message",
                {"channel_id": self.default_channel_id, "text": message},
            )

            return result
        except Exception as e:
            return f"Slack投稿エラー: {str(e)}"

    async def reply_to_slack_thread(
        self, content: str, thread_ts: str, user_id: str
    ) -> str:
        """
        Slackスレッドに返信

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
            tools = await self.tool_manager.list_available_tools()
            tool_names = [tool.name for tool in tools]

            if "slack_reply_to_thread" in tool_names:
                result = await self.tool_manager.execute_tool(
                    "slack_reply_to_thread",
                    {
                        "channel_id": self.default_channel_id,
                        "text": message,
                        "thread_ts": thread_ts,
                    },
                )
                return result
            else:
                # Fallback to regular post with thread_ts
                result = await self.tool_manager.execute_tool(
                    "slack_post_message",
                    {
                        "channel_id": self.default_channel_id,
                        "text": message,
                        "thread_ts": thread_ts,
                    },
                )
                return result

        except Exception as e:
            return f"Slackスレッド返信エラー: {str(e)}"
