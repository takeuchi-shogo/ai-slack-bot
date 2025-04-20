import logging
import os
from typing import Any, Dict, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackService:
    """Slack API操作サービス"""

    def __init__(self):
        # テストモードかどうかを確認
        self.test_mode = os.getenv("TEST_MODE", "False").lower() in ("true", "1", "t")

        # Slack WebClientの初期化
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if not slack_token:
            logger.warning("SLACK_BOT_TOKENが設定されていません")

        self.client = WebClient(token=slack_token) if slack_token else None

    async def send_message(
        self, channel: str, text: str, thread_ts: Optional[str] = None
    ) -> bool:
        """
        Slackにメッセージを送信する

        Args:
            channel: チャンネルID
            text: 送信テキスト
            thread_ts: スレッドタイムスタンプ（オプション）

        Returns:
            送信成功の場合True
        """
        # テキストが空かNoneの場合はデフォルトテキストを使用
        if not text:
            text = "申し訳ありませんが、メッセージを生成できませんでした。"
            logger.warning("送信テキストが空のため、デフォルトテキストを使用します")

        # テストモードの場合はメッセージをログに出力するだけ
        if self.test_mode:
            logger.info(
                f"[テストモード] Slackメッセージ - チャンネル: {channel}, スレッド: {thread_ts}"
            )
            logger.info(f"[テストモード] メッセージ内容: {text}")
            return True

        if not self.client:
            logger.error("Slack clientが初期化されていません")
            return False

        try:
            # メッセージオプションの設定
            options: Dict[str, Any] = {
                "channel": channel,
                "text": text,
            }

            # スレッド指定がある場合
            if thread_ts:
                options["thread_ts"] = thread_ts

            # メッセージを送信
            response = self.client.chat_postMessage(**options)
            return response["ok"]

        except SlackApiError as e:
            logger.error(f"Error sending message to Slack: {e}")
            return False

    def get_permalink(self, channel: str, message_ts: str) -> Optional[str]:
        """
        Slackメッセージへのパーマリンクを取得する

        Args:
            channel: チャンネルID
            message_ts: メッセージタイムスタンプ

        Returns:
            パーマリンクURL、エラー時はNone
        """
        # テストモードの場合はダミーリンクを返す
        if self.test_mode:
            dummy_link = (
                f"https://slack.com/archives/{channel}/p{message_ts.replace('.', '')}"
            )
            logger.info(f"[テストモード] Slackパーマリンク: {dummy_link}")
            return dummy_link

        if not self.client:
            logger.error("Slack clientが初期化されていません")
            return None

        try:
            response = self.client.chat_getPermalink(
                channel=channel, message_ts=message_ts
            )
            return response.get("permalink")
        except SlackApiError as e:
            logger.error(f"Error getting permalink: {e}")
            return None
