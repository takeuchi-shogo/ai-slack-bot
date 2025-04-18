import asyncio
import logging
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from models import MentionTask, MentionSource
from agents.mcp_server import MCPServer

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCPサーバーのインスタンス
mcp_server = MCPServer()


async def process_mention(mention_data: Dict[str, Any]) -> str:
    """
    メンションデータを処理し、適切な応答を返す

    Args:
        mention_data: Slackから受信したメンションのデータ

    Returns:
        メンションへの応答テキスト
    """
    try:
        # メンションタスクを作成
        task = MentionTask(
            source=MentionSource.SLACK,
            text=mention_data.get("text", ""),
            user=mention_data.get("user", "unknown"),
            channel=mention_data.get("channel", ""),
            ts=mention_data.get("ts", ""),
            thread_ts=mention_data.get("thread_ts")
        )
        
        # タスクをログに記録
        logger.info(f"Processing mention from user {task.user}: {task.text}")
        
        # MCPサーバーでタスクを処理
        result = await mcp_server.process(task)
        
        # 処理結果をログに記録
        logger.info(f"Processing result: {result}")
        
        # 処理成功の場合
        if result.get("success", False):
            return "メッセージを処理しました。"
        else:
            error = result.get("error", "不明なエラー")
            logger.error(f"Error in processing: {error}")
            return f"メッセージの処理中にエラーが発生しました: {error}"
            
    except Exception as e:
        logger.error(f"Error in process_mention: {e}")
        return f"メッセージの処理中に予期せぬエラーが発生しました。"


async def main():
    """メインエントリーポイント"""
    logger.info("AI Agent starting...")
    
    # テスト用のメンションデータ
    test_mention = {
        "text": "こんにちは、プロジェクトのログイン機能にバグがあるようです。認証後にリダイレクトが正しく動作していません。",
        "user": "U01234ABC",
        "channel": "C01234XYZ",
        "ts": "1617262456.000200"
    }
    
    # テスト実行
    response = await process_mention(test_mention)
    logger.info(f"Test response: {response}")


if __name__ == "__main__":
    asyncio.run(main())