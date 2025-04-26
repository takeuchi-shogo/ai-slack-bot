from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """アプリケーション設定"""

    PORT: int = Field(default=8080)
    DEBUG: bool = Field(default=False)
    TEST_MODE: bool = Field(default=False)

    # LLM API Keys
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    GOOGLE_API_KEY: str

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
    SQS_ENDPOINT: str = Field(default="http://localhost:9324")
    SQS_QUEUE_NAME: str = Field(default="slack-mentions")

    # LangSmith設定
    LANGSMITH_TRACING: bool = Field(default=False)
    LANGSMITH_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    LANGSMITH_API_KEY: str = Field(default="")
    LANGSMITH_PROJECT: str = Field(default="ai-agent")

    # Database設定
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=3306)
    DB_NAME: str = Field(default="slack_bot")
    DB_USER: str = Field(default="root")
    DB_PASSWORD: str = Field(default="")

    class Config:
        env_file = ".env"
        # 大文字小文字を区別しない（.envファイルの変数名が小文字でも読み込める）
        case_sensitive = False


settings = Settings()
