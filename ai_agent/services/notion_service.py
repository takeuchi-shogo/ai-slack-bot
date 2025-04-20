import logging
import os
import uuid
from typing import Optional

from config import settings
from models import NotionTask
from notion_client import Client

logger = logging.getLogger(__name__)


class NotionService:
    """Notion API操作サービス"""

    def __init__(self):
        # テストモードかどうかを確認
        self.test_mode = os.getenv("TEST_MODE", "False").lower() in ("true", "1", "t")

        # Notion設定の取得
        notion_api_key = os.getenv("NOTION_API_KEY", settings.NOTION_API_KEY)
        self.database_id = os.getenv("NOTION_DATABASE_ID", settings.NOTION_DATABASE_ID)

        # テストモードでなければクライアントを初期化
        if not self.test_mode and notion_api_key:
            self.client = Client(auth=notion_api_key)
        else:
            self.client = None
            if not self.test_mode:
                logger.warning(
                    "Notion API Keyが設定されていないため、Notionクライアントは初期化されません"
                )

    async def create_task(self, task: NotionTask) -> Optional[str]:
        """
        Notionにタスクを作成する

        Args:
            task: 作成するタスク情報

        Returns:
            作成されたページID、失敗した場合はNone
        """
        # テストモードの場合はダミーIDを返す
        if self.test_mode:
            dummy_id = str(uuid.uuid4())
            logger.info(f"[テストモード] Notionタスク作成: {task.title}")
            logger.info(f"[テストモード] タスクID: {dummy_id}")
            return dummy_id

        # クライアントが初期化されていない場合
        if not self.client:
            logger.error("Notionクライアントが初期化されていません")
            return None

        try:
            # タスクをNotionページとして作成
            page = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "タイトル": {"title": [{"text": {"content": task.title}}]},
                    "ステータス": {"select": {"name": "未対応"}},
                },
                children=[
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "概要"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {"type": "text", "text": {"content": task.description}}
                            ]
                        },
                    },
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "手順"}}]
                        },
                    },
                    *[
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": step}}
                                ]
                            },
                        }
                        for step in task.steps
                    ],
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "参照リンク"}}
                            ]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "Slackスレッド: "},
                                    "annotations": {"bold": True},
                                },
                                {
                                    "type": "text",
                                    "text": {
                                        "content": task.slack_url,
                                        "link": {"url": task.slack_url},
                                    },
                                },
                            ]
                        },
                    },
                ],
            )

            return page.get("id")

        except Exception as e:
            logger.error(f"Error creating task in Notion: {e}")
            return None
