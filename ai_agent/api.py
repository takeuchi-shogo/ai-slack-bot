import asyncio
import logging
import os

import uvicorn
from agents.mcp_server import MCPServer
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import MentionRequest, MentionResponse, MentionSource, MentionTask
from services.queue_service import QueueService
from services.slack_service import SlackService

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション
app = FastAPI(title="AI Slack Bot Agent")

# CORSミドルウェア
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# サービスの初期化
slack_service = SlackService()
queue_service = QueueService()
mcp_server = MCPServer()


# 依存性注入
def get_mcp_server():
    return mcp_server


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "service": "ai-slack-bot"}


@app.post("/process-mention", response_model=MentionResponse)
async def handle_mention(
    mention: MentionRequest,
    background_tasks: BackgroundTasks,
    server: MCPServer = Depends(get_mcp_server),
):
    """
    Slackのメンション処理エンドポイント

    Args:
        mention: Slackからのメンションデータ
        background_tasks: バックグラウンドタスク
        server: MCPサーバー

    Returns:
        処理結果
    """
    try:
        # メンションタスクを作成
        task = MentionTask(
            source=MentionSource.SLACK,
            text=mention.text,
            user=mention.user,
            channel=mention.channel,
            ts=mention.ts,
            thread_ts=mention.thread_ts,
        )

        # キューにタスクを送信（非同期処理用）
        queue_success = await queue_service.send_message(task)

        if not queue_success:
            logger.warning("Failed to send message to queue, processing synchronously")

        # 直接処理を実行（同期処理）
        background_tasks.add_task(server.process, task)

        return MentionResponse(
            response="メッセージを受け付けました。処理中です...",
            requires_notion_task=False,
        )

    except Exception as e:
        logger.error(f"Error processing mention: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing mention: {str(e)}"
        )


@app.post("/process-directly")
async def process_directly(
    mention: MentionRequest, server: MCPServer = Depends(get_mcp_server)
):
    """
    メンションを直接処理するエンドポイント（テスト用）

    Args:
        mention: Slackからのメンションデータ
        server: MCPサーバー

    Returns:
        処理結果
    """
    try:
        # メンションタスクを作成
        task = MentionTask(
            source=MentionSource.SLACK,
            text=mention.text,
            user=mention.user,
            channel=mention.channel,
            ts=mention.ts,
            thread_ts=mention.thread_ts,
        )

        # 直接処理を実行
        result = await server.process(task)

        return result

    except Exception as e:
        logger.error(f"Error in direct processing: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in direct processing: {str(e)}"
        )


@app.post("/process-with-mcp")
async def process_with_mcp(
    mention: MentionRequest, server: MCPServer = Depends(get_mcp_server)
):
    """
    MCPツールを使用してメンションを直接処理するエンドポイント

    Args:
        mention: Slackからのメンションデータ
        server: MCPサーバー

    Returns:
        処理結果
    """
    try:
        # メンションタスクを作成
        task = MentionTask(
            source=MentionSource.SLACK,
            text=mention.text,
            user=mention.user,
            channel=mention.channel,
            ts=mention.ts,
            thread_ts=mention.thread_ts,
        )

        # MCPツールで処理を実行
        result = await server.process_with_mcp(task)

        return result

    except Exception as e:
        logger.error(f"Error in MCP processing: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in MCP processing: {str(e)}"
        )


async def start_background_tasks():
    """バックグラウンドタスクを開始する"""
    from agents.mcp_client import MCPClient

    # MCPクライアントの開始
    client = MCPClient()
    await client.run()


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時のイベント"""
    logger.info("Starting AI Slack Bot Agent")

    # バックグラウンドタスクを開始
    asyncio.create_task(start_background_tasks())


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
