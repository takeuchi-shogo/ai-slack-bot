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

        # データベースIDの正規化（ハイフンの有無を許容）
        if self.database_id:
            # ハイフンを削除したIDを取得
            self.database_id_no_hyphens = self.database_id.replace("-", "")
            # 長さに基づいて正しいフォーマットを推測
            if len(self.database_id) < 36 and len(self.database_id_no_hyphens) == 32:
                # ハイフンなしの32文字IDをUUID形式に変換
                formatted_id = f"{self.database_id_no_hyphens[:8]}-{self.database_id_no_hyphens[8:12]}-{self.database_id_no_hyphens[12:16]}-{self.database_id_no_hyphens[16:20]}-{self.database_id_no_hyphens[20:]}"
                logger.info(f"データベースIDをUUID形式に変換しました: {formatted_id}")
                self.database_id = formatted_id

            logger.info(f"使用するNotion Database ID: {self.database_id}")
            logger.info(f"ハイフンなし形式のID: {self.database_id_no_hyphens}")

        # テストモードでなければクライアントを初期化
        if not self.test_mode and notion_api_key:
            self.client = Client(auth=notion_api_key)
            # クライアントの初期化成功を確認
            try:
                # APIが機能するか確認
                self.client.users.me()
                logger.info("Notion APIに正常に接続しました")
            except Exception as e:
                logger.error(f"Notion API接続エラー: {e}")
                self.client = None
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

        # Slack URLが空の場合、デフォルト値を設定
        slack_url = task.slack_url
        if not slack_url:
            slack_url = "https://slack.com"
            logger.warning("Slack URLが空のため、デフォルト値を使用します")

        try:
            # まずハイフン付きの形式で試す
            return await self._try_create_page(task, slack_url, self.database_id)
        except Exception as e:
            logger.warning(f"ハイフン付きIDでの作成に失敗しました: {e}")

            # 失敗したらハイフンなしの形式で試す
            try:
                if hasattr(self, "database_id_no_hyphens"):
                    logger.info(
                        f"ハイフンなしIDで再試行: {self.database_id_no_hyphens}"
                    )
                    return await self._try_create_page(
                        task, slack_url, self.database_id_no_hyphens
                    )
                else:
                    logger.error("ハイフンなしIDが設定されていません")
                    return None
            except Exception as e2:
                logger.error(f"ハイフンなしIDでも失敗しました: {e2}")
                return None

    async def _try_create_page(
        self, task: NotionTask, slack_url: str, db_id: str
    ) -> Optional[str]:
        """
        指定されたデータベースIDでページ作成を試みる

        Args:
            task: 作成するタスク情報
            slack_url: SlackのURL
            db_id: 使用するデータベースID

        Returns:
            作成されたページID、失敗した場合はNone
        """
        try:
            # データベースIDの使用をログに記録
            logger.info(f"Notion DB ID '{db_id}' でページ作成を試みます")

            # タスクをNotionページとして作成
            page = self.client.pages.create(
                parent={"database_id": db_id},
                properties={
                    "タイトル": {"title": [{"text": {"content": task.title}}]},
                    "ステータス": {"status": {"name": "未着手"}},
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
                                        "content": slack_url,
                                        "link": {"url": slack_url},
                                    },
                                },
                            ]
                        },
                    },
                ],
            )

            page_id = page.get("id")
            logger.info(f"Notionにタスクを作成しました: {task.title}, ID: {page_id}")
            return page_id

        except Exception as e:
            logger.error(f"Notion ページ作成エラー (DB ID: {db_id}): {e}")
            # 例外を伝播させる
            raise
