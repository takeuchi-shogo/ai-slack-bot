import logging
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import settings

logger = logging.getLogger(__name__)


class SlackService:
    """Slack API操作サービス"""

    def __init__(self):
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)

    async def send_message(
        self, channel: str, text: str, thread_ts: Optional[str] = None
    ) -> bool:
        """
        Slackメッセージを送信する

        Args:
            channel: メッセージを送信するチャンネルID
            text: 送信するテキスト
            thread_ts: スレッドのタイムスタンプ (スレッド返信の場合)

        Returns:
            送信成功したかどうか
        """
        try:
            kwargs = {"channel": channel, "text": text}

            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            response = self.client.chat_postMessage(**kwargs)
            return True

        except SlackApiError as e:
            logger.error(f"Error sending message to Slack: {e}")
            return False

    def get_permalink(self, channel: str, message_ts: str) -> Optional[str]:
        """
        メッセージのパーマリンクを取得する

        Args:
            channel: チャンネルID
            message_ts: メッセージのタイムスタンプ

        Returns:
            パーマリンクURL、取得できない場合はNone
        """
        try:
            response = self.client.chat_getPermalink(
                channel=channel, message_ts=message_ts
            )
            return response.get("permalink")

        except SlackApiError as e:
            logger.error(f"Error getting permalink: {e}")
            return None
