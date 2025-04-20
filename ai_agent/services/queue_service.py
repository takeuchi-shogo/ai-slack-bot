import json
import logging
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from config import settings
from models import MentionTask

logger = logging.getLogger(__name__)


class QueueService:
    """SQSキュー操作サービス"""

    def __init__(self):
        # テストモードかどうかを確認
        self.test_mode = os.getenv("TEST_MODE", "False").lower() in ("true", "1", "t")

        # テストモードの場合は初期化をスキップ
        if self.test_mode:
            logger.info(
                "テストモードのため、ElasticMQクライアントの初期化をスキップします"
            )
            self.queue = None
            self.queue_name = settings.SQS_QUEUE_NAME
            return

        # ElasticMQへの接続設定
        endpoint_url = settings.SQS_ENDPOINT
        self.queue_name = settings.SQS_QUEUE_NAME

        logger.info(
            f"ElasticMQ接続設定 - エンドポイント: {endpoint_url}, キュー名: {self.queue_name}"
        )

        try:
            self.sqs = boto3.resource(
                "sqs",
                endpoint_url=endpoint_url,
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            # 利用可能なキューを表示
            try:
                all_queues = list(self.sqs.queues.all())
                queue_urls = [q.url for q in all_queues]
                logger.info(f"利用可能なキュー: {queue_urls}")
            except Exception as e:
                logger.warning(f"キュー一覧の取得中にエラーが発生しました: {e}")

            # キューの取得を試みる
            try:
                self.queue = self.sqs.get_queue_by_name(QueueName=self.queue_name)
                logger.info(
                    f"キュー '{self.queue_name}' への接続に成功しました: {self.queue.url}"
                )
            except ClientError as e:
                if (
                    e.response["Error"]["Code"]
                    == "AWS.SimpleQueueService.NonExistentQueue"
                ):
                    logger.warning(
                        f"キュー '{self.queue_name}' が存在しません。新規作成を試みます..."
                    )
                    try:
                        self.queue = self.sqs.create_queue(QueueName=self.queue_name)
                        logger.info(
                            f"キュー '{self.queue_name}' を作成しました: {self.queue.url}"
                        )
                    except Exception as create_err:
                        logger.error(f"キューの作成に失敗しました: {create_err}")
                        self.queue = None
                else:
                    logger.error(f"キューへの接続に失敗しました: {e}")
                    self.queue = None
        except Exception as e:
            # 開発モードでは警告だけ表示して続行
            if os.getenv("DEBUG", "False").lower() in ("true", "1", "t"):
                logger.warning(
                    f"ElasticMQへの接続に失敗しました (開発モードで続行): {e}"
                )
                self.queue = None
            else:
                # 本番環境ではエラーを発生させる
                logger.error(f"ElasticMQへの接続に失敗しました: {e}")
                raise

    async def send_message(self, task: MentionTask) -> bool:
        """
        キューにメッセージを送信する

        Args:
            task: 送信するタスク

        Returns:
            送信成功したかどうか
        """
        # テストモードまたはキュー未初期化の場合
        if self.test_mode:
            logger.info(f"[テストモード] メッセージ送信: {task.text}")
            return True

        # キューが初期化されていない場合は失敗
        if self.queue is None:
            logger.warning("キューが初期化されていないため、メッセージは送信されません")
            return False

        try:
            message_body = task.json()
            response = self.queue.send_message(MessageBody=message_body)
            logger.info(
                f"メッセージをキューに送信しました: {response.get('MessageId')}"
            )
            return True
        except Exception as e:
            logger.error(f"キューへのメッセージ送信エラー: {e}")
            return False

    async def receive_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        キューからメッセージを受信する

        Args:
            max_messages: 最大受信メッセージ数

        Returns:
            受信したメッセージのリスト
        """
        # テストモードの場合は空のリストを返す
        if self.test_mode:
            logger.info("[テストモード] メッセージ受信をスキップします")
            return []

        # キューが初期化されていない場合は空リストを返す
        if self.queue is None:
            logger.warning(
                "キューが初期化されていないため、空のメッセージリストを返します"
            )
            return []

        try:
            messages = []
            sqs_messages = self.queue.receive_messages(
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=20,  # ロングポーリング
            )

            logger.info(f"キューから {len(sqs_messages)} 件のメッセージを受信しました")

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
                    logger.info(
                        f"メッセージID {message.message_id} を処理して削除しました"
                    )
                except json.JSONDecodeError:
                    logger.error(f"不正なJSON形式のメッセージ: {message.body}")
                    message.delete()  # 不正なメッセージも削除

            return messages

        except Exception as e:
            logger.error(f"キューからのメッセージ受信エラー: {e}")
            return []
