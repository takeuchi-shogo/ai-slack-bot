"""
設定管理モジュール

環境変数の読み込みやアプリケーション全体の設定を管理します
"""

import json
import os

from dotenv import load_dotenv

# 環境変数のロード
load_dotenv()  # load environment variables from .env

# モデル設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# モデル名の定数
ANTHROPIC_MODEL_NAME = "claude-3-5-sonnet-20241022"
GEMINI_MODEL_NAME = "gemini-1.5-pro"


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
