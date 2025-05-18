from typing import List

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class Message(BaseModel):
    agent_name: str = Field(default="", description="Agentの名前")
    message: BaseMessage = Field(default="", description="Agentのメッセージ")


class State(BaseModel):
    """エージェントの状態を定義するクラス"""

    """ユーザーからのクエリ"""
    query: str = Field(default="", description="ユーザーからのクエリ")
    """LLMのメッセージ"""
    messages: List[Message] = Field(default=[], description="LLMのメッセージ")
    """DBなど他のエージェントからのデータが必要かのフラグ"""
    is_need_data: bool = Field(
        default=False, description="DBなど他のエージェントからのデータが必要かのフラグ"
    )
    """データベースのSQLクエリ"""
    sql_query: str = Field(default="", description="データベースのSQLクエリ")
    """データベースからのデータ"""
    database_result: str = Field(default="", description="データベースからのデータ")
    """ロガーからのデータ"""
    logger_result: str = Field(default="", description="ロガーからのデータ")
    """データの要約"""
    data_summary: str = Field(default="", description="データの要約")
    """コードレビューが必要かのフラグ"""
    is_need_code_review: bool = Field(
        default=False, description="コードレビューが必要かのフラグ"
    )
    """コードレビューの結果"""
    code_review_result: str = Field(default="", description="コードレビューの結果")
