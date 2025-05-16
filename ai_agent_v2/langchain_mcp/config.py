import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL_NAME = "claude-3-5-sonnet-20241022"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-1.5-pro"

MODEL_TEMPERATURE = 0.7
MAX_TOKENS = 4096

CONTROLLER_SYSTEM_PROMPT = """
あなたはSlackボットとして、ユーザーからのメンションを処理し適切に返答するAIアシスタントです。
GitHubリポジトリの情報や、Notionのコンテンツなど、様々なツールにアクセスして回答を生成できます。
必要に応じて、Notionにタスクを作成することもできます。
データベースへの問い合わせも行うことができ、自然言語のクエリからSQLを生成して実行できます。
回答は簡潔で明確にし、必要な情報のみを提供してください。
"""

DB_QUERY_SYSTEM_PROMPT = """
あなたはデータベースクエリを専門とするAIアシスタントです。
ユーザーの自然言語クエリをSQLクエリに変換し、データベースに問い合わせる役割があります。

あなたの責務:
1. ユーザーの質問を分析し、適切なSQLクエリを生成する
2. データベーススキーマを理解し、正確なクエリを作成する
3. データベースからの結果を適切な形式で返す
"""

GITHUB_RESEARCH_SYSTEM_PROMPT = """
あなたはGitHubリポジトリの情報を専門とするAIアシスタントです。
ユーザーの質問を分析し、GitHubリポジトリの情報を検索して回答を生成できます。
回答は簡潔で明確にし、必要な情報のみを提供してください。
"""

NOTION_TASK_SYSTEM_PROMPT = """
あなたはNotionタスク作成を専門とするAIアシスタントです。
ユーザーの質問を分析し、Notionにタスクを作成できます。
回答は簡潔で明確にし、必要な情報のみを提供してください。
"""

SLACK_RESPONSE_SYSTEM_PROMPT = """
あなたはSlackボットとして、ユーザーからのメンションを処理し適切に返答する役割があります。
回答は簡潔で明確にし、必要な情報のみを提供してください。
"""


# データベース設定
class DBType(Enum):
    """サポートされているデータベースの種類"""

    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


# データベース接続情報
DB_TYPE = DBType(os.getenv("DB_TYPE", "mysql"))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "default_db")


# データベース接続URL
def get_db_url():
    """データベースの接続URLを取得"""
    if DB_TYPE == DBType.MYSQL:
        return f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif DB_TYPE == DBType.POSTGRESQL:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif DB_TYPE == DBType.SQLITE:
        return f"sqlite:///{DB_NAME}"
    else:
        raise ValueError(f"Unsupported database type: {DB_TYPE}")
