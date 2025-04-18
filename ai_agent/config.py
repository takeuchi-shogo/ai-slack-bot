import os
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """アプリケーション設定"""
    PORT: int = Field(default=8080)
    DEBUG: bool = Field(default=False)
    
    # LLM API Keys
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    
    # Slack Integration
    SLACK_BOT_TOKEN: str
    SLACK_APP_TOKEN: str
    
    # Notion Integration
    NOTION_API_KEY: str
    NOTION_DATABASE_ID: str
    
    # AWS / ElasticMQ
    AWS_ACCESS_KEY_ID: str = Field(default="dummy")
    AWS_SECRET_ACCESS_KEY: str = Field(default="dummy")
    AWS_REGION: str = Field(default="us-east-1")
    SQS_ENDPOINT: str = Field(default="http://elasticmq:9324")
    SQS_QUEUE_NAME: str = Field(default="slack-mentions")
    
    class Config:
        env_file = ".env"


settings = Settings()