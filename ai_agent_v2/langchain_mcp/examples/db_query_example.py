#!/usr/bin/env python3
"""
データベースクエリ機能のサンプルコード

このサンプルでは、自然言語クエリからSQLを生成し、
データベースに問い合わせを行う機能をテストします。
LangChainを使った直接接続による実装を示します。
"""

import asyncio
import logging
import os
import sys

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# プロジェクトルートを追加（このスクリプトを直接実行する場合に必要）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.database import DatabaseAgent
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()


async def test_db_query():
    """
    データベース接続でクエリを実行する例
    """
    print("\n=== データベースクエリのテスト ===\n")

    # DatabaseAgentを初期化
    db_agent = DatabaseAgent()

    # サンプルクエリ
    queries = [
        "ユーザー数は何人ですか？",
        "最近30日以内に作成されたユーザーを一覧表示して",
        "最も投稿数が多いユーザーは誰ですか？",
    ]

    for query in queries:
        print(f"\n自然言語クエリ: {query}")
        try:
            result = await db_agent.process_query(query)

            print(f"生成されたSQL: {result.get('sql', 'なし')}")

            if "error" in result:
                print(f"エラー: {result['error']}")
            else:
                print("応答:")
                print(result.get("response", "応答なし"))
        except Exception as e:
            print(f"エラー: {str(e)}")

    # リソースの解放
    await db_agent.close()


async def main():
    """メイン関数"""
    # データベースクエリのテスト
    await test_db_query()


if __name__ == "__main__":
    asyncio.run(main())
