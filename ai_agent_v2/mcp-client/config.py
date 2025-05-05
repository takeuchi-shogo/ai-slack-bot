"""
設定管理モジュール

環境変数の読み込みやアプリケーション全体の設定を管理します
LangChain関連の設定も含む
データベース接続設定も含む
"""

import json
import os
from enum import Enum

from dotenv import load_dotenv

# 環境変数のロード
load_dotenv()  # load environment variables from .env

# モデル設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# モデル名の定数
ANTHROPIC_MODEL_NAME = "claude-3-5-sonnet-20241022"
GEMINI_MODEL_NAME = "gemini-1.5-pro"

# LangChain関連の設定
# モデル設定の温度 (0.0〜1.0)
MODEL_TEMPERATURE = 0.7
# トークン制限
MAX_TOKENS = 4096
# システムプロンプト
SYSTEM_PROMPT = """
あなたはSlackボットとして、ユーザーからのメンションを処理し適切に返答するAIアシスタントです。
GitHubリポジトリの情報や、Notionのコンテンツなど、様々なツールにアクセスして回答を生成できます。
必要に応じて、Notionにタスクを作成することもできます。
データベースへの問い合わせも行うことができ、自然言語のクエリからSQLを生成して実行できます。
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


# データベーススキーマ説明
DB_SCHEMA_DESCRIPTION = os.getenv(
    "DB_SCHEMA_DESCRIPTION",
    """
このデータベースには以下のテーブルがあります:
- users: ユーザー情報を管理（id, name, email, created_at）
- projects: プロジェクト情報を管理（id, title, description, user_id, created_at）
- tasks: タスク情報を管理（id, title, description, status, project_id, assigned_to, created_at）
""",
)


# サーバースキーマ関連
def get_schema_path(server_name):
    """スキーマファイルのパスを取得"""
    schema_dir = os.path.join(os.path.dirname(__file__), "schema")
    return os.path.join(schema_dir, f"{server_name}.json")


def load_server_schema(server_name):
    """サーバースキーマをロード"""
    schema_file = get_schema_path(server_name)

    if not os.path.exists(schema_file):
        raise ValueError(f"Schema file for {server_name} not found at {schema_file}")

    with open(schema_file, "r") as f:
        return json.load(f)


def get_server_config(schema, server_name):
    """スキーマからサーバー設定を取得"""
    if server_name not in schema.get("mcpServers", {}):
        raise ValueError(f"Server '{server_name}' not found in schema file")

    return schema["mcpServers"][server_name]


# チャンネルIDの取得
def extract_default_channel_id(env):
    """環境変数からデフォルトのチャンネルIDを抽出"""
    if "SLACK_CHANNEL_IDS" in env:
        return env["SLACK_CHANNEL_IDS"].split(",")[0].strip()
    return None
