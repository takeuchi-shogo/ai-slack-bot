import asyncio
import logging

from client.agent import AgentClient

logger = logging.getLogger(__name__)


async def main():
    """メイン処理"""
    logger.info("Hello from agents!")
    client = AgentClient()
    query = """
    こんにちわ
    """
    await client.run(query, channel_id="C062T1JP41M", thread_ts="")
    logger.info("処理が正常に完了しました")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("アプリケーションが中断されました")
    except Exception as e:
        logger.error(f"致命的なエラー: {e}")
        import traceback

        logger.error(f"スタックトレース: {traceback.format_exc()}")
        import sys

        sys.exit(1)
