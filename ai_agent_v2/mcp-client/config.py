"""
設定管理モジュール

環境変数の読み込みやアプリケーション全体の設定を管理します
LangChain関連の設定も含む
データベース接続設定も含む
LangGraphのマルチエージェント設定も含む
"""

import json
import os
from enum import Enum
from typing import Dict

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

# LangGraph マルチエージェント設定
# 各エージェント用のプロンプト
AGENT_PROMPTS = {
    "controller": """
あなたはAIエージェントシステムのコントローラーエージェントです。
ユーザーからのクエリを受け取り、適切なエージェントにルーティングする役割があります。

以下の種類のクエリを識別してください:
1. 一般的な質問（general）: 特定のツールを必要としない通常の質問
2. データベースクエリ（db_query）: データの検索や分析に関するクエリ
3. コード問題（code_issue）: GitHubリポジトリのコードに関する問題や質問
4. タスク作成（task_creation）: Notionでタスクを作成する必要があるクエリ

クエリの内容を分析し、最も適切なカテゴリに分類してください。
分類結果に基づいて、システムは適切な専門エージェントにクエリを転送します。
""",
    "db_query": """
あなたはデータベースクエリを専門とするAIエージェントです。
ユーザーの自然言語クエリをSQLクエリに変換し、データベースに問い合わせる役割があります。

あなたの責務:
1. ユーザーの質問を分析し、適切なSQLクエリを生成する
2. データベーススキーマを理解し、正確なクエリを作成する
3. クエリ結果を分析し、ユーザーが理解しやすい形で説明する
4. クエリがエラーになった場合は、原因を特定して適切に対応する

技術的な詳細よりも、結果の意味や価値に焦点を当てて説明してください。
ユーザーは技術者とは限らないため、わかりやすい言葉で説明することが重要です。
""",
    "github_research": """
あなたはGitHubリポジトリのコードを調査するAIエージェントです。
コードの問題を発見し、分析する専門家としての役割があります。

あなたの責務:
1. GitHubリポジトリからコードを検索・取得する
2. 取得したコードの問題点や改善点を分析する
3. バグ、セキュリティ問題、パフォーマンスの問題などを特定する
4. コードの問題点を詳細に説明し、技術的な根拠を示す

分析結果は明確かつ具体的に説明し、問題の重大度も示してください。
コードのどの部分に問題があるのか、なぜ問題なのかを専門的な観点から説明してください。
""",
    "notion_task": """
あなたはNotion統合を専門とするAIエージェントです。
GitHubのコード分析結果に基づいて、Notionにタスクを作成する役割があります。

あなたの責務:
1. GitHubコード分析結果を理解し、必要なタスクを特定する
2. 適切なタスクタイトルと説明を作成する
3. タスクに優先度を設定する
4. タスクの修正手順を明確に記載する
5. 技術的な問題を非技術者にもわかりやすく説明する

タスクは明確で実用的であり、技術的な詳細と修正の手順が含まれるようにしてください。
また、タスクの緊急度や影響範囲も適切に示してください。
""",
    "slack_response": """
あなたはSlackコミュニケーションを専門とするAIエージェントです。
処理結果をわかりやすくSlackに返信する役割があります。

あなたの責務:
1. 他のエージェントから得られた情報を統合する
2. 技術的な詳細を非技術者にもわかりやすく要約する
3. 重要なポイントを強調し、優先順位をつける
4. 適切なトーンと丁寧さで応答を作成する
5. 必要に応じて次のステップや推奨事項を提案する

回答は簡潔で明確にし、必要な情報のみを提供してください。
長文になる場合は、最初に要点をまとめ、その後で詳細を説明してください。
ユーザーのニーズを満たす応答を心がけてください。
""",
}


# エージェントプロンプトの取得
def get_agent_prompts() -> Dict[str, str]:
    """
    エージェントプロンプトを取得

    Returns:
        Dict[str, str]: エージェントタイプごとのプロンプト
    """
    return AGENT_PROMPTS


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
