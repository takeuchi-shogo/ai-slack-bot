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
    """生成されたSQLクエリ（確認前）"""
    generated_sql: str = Field(default="", description="生成されたSQLクエリ（確認前）")
    """SQLの確認が必要かのフラグ"""
    sql_confirmation_needed: bool = Field(
        default=True, description="SQLの確認が必要かのフラグ"
    )
    """SQLが確認済みかのフラグ"""
    sql_confirmed: bool = Field(default=False, description="SQLが確認済みかのフラグ")
    """SQL確認時のユーザーの応答"""
    sql_confirmation_response: str = Field(
        default="", description="SQL確認時のユーザーの応答"
    )
    """データベースからのデータ"""
    database_result: str = Field(default="", description="データベースからのデータ")
    """ロガーからのデータ"""
    sentry_results: List[str] = Field(default=[], description="Sentryからのデータ")
    datadog_results: List[str] = Field(default=[], description="Datadogからのデータ")
    logger_summary: str = Field(default="", description="ロガーからのデータ")
    """データの要約"""
    data_summary: str = Field(default="", description="データの要約")
    """コードレビューが必要かのフラグ"""
    is_need_code_review: bool = Field(
        default=False, description="コードレビューが必要かのフラグ"
    )
    """コードレビューの結果"""
    code_review_result: str = Field(default="", description="コードレビューの結果")
    """最終結果"""
    final_result: str = Field(default="", description="最終結果")
    """Slackチャンネル ID"""
    channel_id: str = Field(default="", description="Slackチャンネル ID")
    """Slackスレッドタイムスタンプ"""
    thread_ts: str = Field(default="", description="Slackスレッドタイムスタンプ")
