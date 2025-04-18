import asyncio
import logging
from typing import Any, Dict

from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_anthropic import ChatAnthropicMessages

from ..config import settings
from ..models import MentionTask, TaskAnalysisResult
from ..services.queue_service import QueueService

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP クライアント"""

    def __init__(self):
        self.queue_service = QueueService()
        self.llm = ChatAnthropicMessages(
            model="claude-3-opus-20240229",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.1,
        )

        # プロンプトテンプレート
        self.analyze_prompt = PromptTemplate.from_template(
            """
            あなたは、Slackのメンションを分析するAIアシスタントです。
            以下のメンションの内容を分析し、適切な対応を決定してください。
            
            # メンション内容
            {text}
            
            # 分析の手順
            1. メンションの意図や要求を理解する
            2. 対応が必要かどうかを判断する
            3. Notion追加タスクとして詳細な調査や対応が必要かを判断する
            
            # 回答形式
            回答は以下の2つの部分から構成されます：
            1. Slackへの返信内容 - ユーザーに直接返信する内容（簡潔に）
            2. 後続アクションの要否 - NotionにタスクとしてトラッキングすべきかどうかのTrue/False
            
            出力形式：
            ```
            回答: [Slackへの返信内容]
            要フォローアップ: [True/False]
            ```
            """
        )

        # LangChainチェーン
        self.chain = self.analyze_prompt | self.llm | StrOutputParser()

    async def run(self, interval: int = 30) -> None:
        """
        一定間隔でキューのメッセージをポーリングする

        Args:
            interval: ポーリング間隔（秒）
        """
        logger.info("Starting MCP client poller...")

        while True:
            try:
                # キューからメッセージを受信
                messages = await self.queue_service.receive_messages()

                if messages:
                    logger.info(f"Received {len(messages)} messages")

                    # 非同期でタスクを処理
                    tasks = [self.process_message(message) for message in messages]
                    await asyncio.gather(*tasks)

                # 次のポーリングまで待機
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(interval)

    async def process_message(self, message: Dict[str, Any]) -> None:
        """
        メッセージを処理する

        Args:
            message: 処理するメッセージ
        """
        try:
            body = message.get("body", {})
            task = MentionTask(**body)

            # メッセージ内容の分析
            result = await self.analyze_message(task.text)

            # 結果をサーバーに送信
            # TODO: 実装

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def analyze_message(self, text: str) -> TaskAnalysisResult:
        """
        メッセージを分析する

        Args:
            text: 分析するテキスト

        Returns:
            分析結果
        """
        try:
            # LLMでメッセージを分析
            result = await self.chain.ainvoke({"text": text})

            # 結果のパース
            lines = result.strip().split("\n")
            content = ""
            requires_follow_up = False

            for line in lines:
                if line.startswith("回答:"):
                    content = line.replace("回答:", "").strip()
                elif line.startswith("要フォローアップ:"):
                    follow_up_text = (
                        line.replace("要フォローアップ:", "").strip().lower()
                    )
                    requires_follow_up = follow_up_text == "true"

            return TaskAnalysisResult(
                content=content, requires_follow_up=requires_follow_up
            )

        except Exception as e:
            logger.error(f"Error analyzing message: {e}")
            return TaskAnalysisResult(
                content="メッセージの分析中にエラーが発生しました。後ほど再度お試しください。",
                requires_follow_up=False,
            )
