import asyncio
import logging
import signal
from typing import Any, Dict

from agents.db_agent import DatabaseAgent
from agents.mcp_client import MCPClient
from agents.mcp_server import MCPServer
from config import settings
from dotenv import load_dotenv
from models import MentionSource, MentionTask
from services.db_service import DBService
from services.queue_service import QueueService

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# テストモードかどうかを確認
TEST_MODE = settings.TEST_MODE
if TEST_MODE:
    logger.info("テストモードで実行します")

# サービスインスタンスの初期化
mcp_server = MCPServer()
mcp_client = MCPClient()
db_agent = DatabaseAgent()

# ElasticMQが必要かどうかを確認（テストモードでは不要）
if not TEST_MODE:
    queue_service = QueueService()
    db_service = DBService()

# 終了フラグ
shutdown_flag = False


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
            thread_ts=mention_data.get("thread_ts"),
        )

        # タスクをログに記録
        logger.info(f"Processing mention from user {task.user}: {task.text}")

        # DBクエリが必要かどうかを判断するための簡易チェック
        needs_db_query = any(
            keyword in task.text.lower()
            for keyword in [
                "sql",
                "query",
                "データベース",
                "db",
                "select",
                "database",
                "テーブル",
            ]
        )

        if needs_db_query:
            # データベースエージェントでタスクを処理
            logger.info("データベースクエリのリクエストとして処理します")
            result = await db_agent.process(task)

            # 処理結果をログに記録
            logger.info(f"DB Agent processing result: {result}")

            if result.get("success", False):
                # DBエージェントからの応答を生成
                query_result = result.get("query_result", {})

                if query_result.get("query_modified", False):
                    # クエリが修正された場合
                    return f"元のクエリに問題があったため修正して実行しました。\n元クエリ: {query_result.get('original_query', '')}\n実行クエリ: {query_result.get('executed_query', '')}\n結果: {query_result.get('results', [])}"
                else:
                    # クエリが正常だった場合
                    return f"クエリを実行しました。\n{query_result.get('executed_query', '')}\n結果: {query_result.get('results', [])}"
            else:
                error = result.get("error", "不明なエラー")
                logger.error(f"Error in DB processing: {error}")
                return f"データベースクエリの処理中にエラーが発生しました: {error}"
        else:
            # MCPサーバーでタスクを処理（MCP対応版）
            result = await mcp_server.process_with_mcp(task)

            # 処理結果をログに記録
            logger.info(f"MCP processing result: {result}")

            # 処理成功の場合
            if result.get("success", False):
                return "メッセージを処理しました。"
            else:
                error = result.get("error", "不明なエラー")
                logger.error(f"Error in MCP processing: {error}")
                return f"メッセージの処理中にエラーが発生しました: {error}"

    except Exception as e:
        logger.error(f"Error in process_mention: {e}")
        return "メッセージの処理中に予期せぬエラーが発生しました。"


async def poll_elasticmq(interval: int = 10) -> None:
    """
    ElasticMQからメッセージをポーリングする

    Args:
        interval: ポーリング間隔（秒）
    """
    # テストモードではElasticMQポーリングをスキップ
    if TEST_MODE:
        logger.info("テストモードのため、ElasticMQポーリングをスキップします")
        return

    logger.info("Starting ElasticMQ poller...")

    while not shutdown_flag:
        try:
            # キューからメッセージを受信
            messages = await queue_service.receive_messages(max_messages=10)

            if messages:
                logger.info(f"Received {len(messages)} messages from ElasticMQ")

                # 各メッセージを処理
                tasks = []
                for message in messages:
                    try:
                        body = message.get("body", {})
                        task = MentionTask(**body)

                        # MCP処理タスクを追加
                        tasks.append(
                            process_mention(
                                {
                                    "text": task.text,
                                    "user": task.user,
                                    "channel": task.channel,
                                    "ts": task.ts,
                                    "thread_ts": task.thread_ts,
                                }
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error parsing message: {e}")

                # 並行処理を実行
                if tasks:
                    await asyncio.gather(*tasks)

            # 次のポーリングまで待機
            await asyncio.sleep(interval)

        except Exception as e:
            logger.error(f"Error polling ElasticMQ: {e}")
            await asyncio.sleep(interval)


def handle_shutdown(sig, frame):
    """
    シャットダウンハンドラー
    """
    logger.info(f"Received signal {sig}, shutting down...")
    global shutdown_flag
    shutdown_flag = True


async def main():
    """メインエントリーポイント"""
    logger.info("AI Agent starting...")

    # シャットダウンハンドラーを設定
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # ElasticMQポーリングを開始（テストモードでなければ）
    elasticmq_poller = asyncio.create_task(poll_elasticmq())

    # DBサービスの初期化（テストモードでなければ）
    if not TEST_MODE:
        try:
            await db_service.initialize()
            logger.info("DBサービスを初期化しました")
        except Exception as e:
            logger.error(f"DBサービスの初期化に失敗しました: {e}")

    # テストモードの場合のみテスト実行
    if TEST_MODE:
        logger.info("テストモードで実行中: サンプルメンションを処理します")

        # 標準メンションのテスト
        test_mention = {
            "text": "こんにちは、プロジェクトのログイン機能にバグがあるようです。認証後にリダイレクトが正しく動作していません。",
            "user": "U01234ABC",
            "channel": "general",
            "ts": "1617262456.000200",
        }

        # テスト実行
        response = await process_mention(test_mention)
        logger.info(f"標準メンションテスト応答: {response}")

        # DBクエリメンションのテスト
        db_test_mention = {
            "text": "ユーザーテーブルから最新の10件のレコードを取得してください。SELECT * FROM users LIMIT 10",
            "user": "U01234ABC",
            "channel": "database",
            "ts": "1617262456.000300",
        }

        # DBクエリテスト実行
        db_response = await process_mention(db_test_mention)
        logger.info(f"DBクエリテスト応答: {db_response}")

        # 不正なSQLクエリのテスト
        invalid_query_mention = {
            "text": "ユーザーとその注文情報を取得してください。SELECT * FORM users JOIN order ON user.id = orders.user_id",
            "user": "U01234ABC",
            "channel": "database",
            "ts": "1617262456.000400",
        }

        # 不正クエリテスト実行
        invalid_response = await process_mention(invalid_query_mention)
        logger.info(f"不正クエリテスト応答: {invalid_response}")

        # テストモードでは終了
        logger.info("テストが完了しました。終了します。")
        return

    try:
        # テストモードでなければポーリングタスクが終了するまで待機
        await elasticmq_poller
    except asyncio.CancelledError:
        logger.info("ElasticMQ poller was cancelled")

    # DBサービスの終了処理（テストモードでなければ）
    if not TEST_MODE:
        try:
            await db_service.close()
            logger.info("DBサービスを終了しました")
        except Exception as e:
            logger.error(f"DBサービスの終了に失敗しました: {e}")

    logger.info("AI Agent shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
