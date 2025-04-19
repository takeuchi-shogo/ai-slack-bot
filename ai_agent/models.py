import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MentionSource(str, Enum):
    """メンションのソース"""

    SLACK = "slack"
    OTHER = "other"


class MentionRequest(BaseModel):
    """Slackメンションリクエスト"""

    text: str
    user: str
    channel: str
    ts: str
    thread_ts: Optional[str] = None


class MentionResponse(BaseModel):
    """メンション応答"""

    response: str
    requires_notion_task: bool = False
    notion_task_details: Optional[Dict[str, Any]] = None


class MentionTask(BaseModel):
    """処理用メンションタスク"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: MentionSource = MentionSource.SLACK
    text: str
    user: str
    channel: str
    ts: str
    thread_ts: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class TaskAnalysisResult(BaseModel):
    """タスク分析結果"""

    content: str
    requires_follow_up: bool = False


class NotionTask(BaseModel):
    """Notion用タスク"""

    title: str
    description: str
    steps: List[str]
    slack_url: str
