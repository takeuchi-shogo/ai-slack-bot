import json
import logging
from typing import Any, Dict, List

import boto3

from ..config import settings
from ..models import MentionTask

logger = logging.getLogger(__name__)


class QueueService:
    """SQSキュー操作サービス"""

    def __init__(self):
        # ElasticMQへの接続設定
        self.sqs = boto3.resource(
            "sqs",
            endpoint_url=settings.SQS_ENDPOINT,
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.queue_name = settings.SQS_QUEUE_NAME
        self.queue = self.sqs.get_queue_by_name(QueueName=self.queue_name)

    async def send_message(self, task: MentionTask) -> bool:
        """
        キューにメッセージを送信する

        Args:
            task: 送信するタスク

        Returns:
            送信成功したかどうか
        """
        try:
            response = self.queue.send_message(MessageBody=task.json())
            return True
        except Exception as e:
            logger.error(f"Error sending message to queue: {e}")
            return False

    async def receive_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        キューからメッセージを受信する

        Args:
            max_messages: 最大受信メッセージ数

        Returns:
            受信したメッセージのリスト
        """
        try:
            messages = []
            sqs_messages = self.queue.receive_messages(
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=20,  # ロングポーリング
            )

            for message in sqs_messages:
                try:
                    body = json.loads(message.body)
                    messages.append(
                        {
                            "message_id": message.message_id,
                            "receipt_handle": message.receipt_handle,
                            "body": body,
                        }
                    )
                    # 処理したメッセージを削除
                    message.delete()
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in message: {message.body}")
                    message.delete()  # 不正なメッセージも削除

            return messages

        except Exception as e:
            logger.error(f"Error receiving messages from queue: {e}")
            return []
