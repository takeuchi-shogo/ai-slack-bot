import logging
from typing import Optional

from notion_client import Client

from ..config import settings
from ..models import NotionTask

logger = logging.getLogger(__name__)


class NotionService:
    """Notion API操作サービス"""

    def __init__(self):
        self.client = Client(auth=settings.NOTION_API_KEY)
        self.database_id = settings.NOTION_DATABASE_ID

    async def create_task(self, task: NotionTask) -> Optional[str]:
        """
        Notionにタスクを作成する

        Args:
            task: 作成するタスク情報

        Returns:
            作成されたページID、失敗した場合はNone
        """
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
