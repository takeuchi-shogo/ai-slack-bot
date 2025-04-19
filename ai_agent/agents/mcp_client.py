import asyncio
import json
import logging
from typing import Any, Dict, Optional

from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_anthropic import ChatAnthropicMessages
from langchain_core.tools import tool

from ..config import settings
from ..models import MentionTask, NotionTask, TaskAnalysisResult
from ..services.notion_service import NotionService
from ..services.queue_service import QueueService
from ..services.slack_service import SlackService

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP クライアント"""

    def __init__(self):
        self.queue_service = QueueService()
        self.notion_service = NotionService()
        self.slack_service = SlackService()

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

        # MCPツールの設定
        self._register_mcp_tools()

    def _register_mcp_tools(self):
        """MCP用のツールを登録する"""

        @tool("create_notion_task")
        def create_notion_task(
            title: str, description: str, steps: list, slack_url: str
        ) -> str:
            """
            Notionにタスクを作成する

            Args:
                title: タスクのタイトル
                description: タスクの説明
                steps: タスク完了のためのステップ（リスト形式）
                slack_url: 関連するSlackスレッドURL

            Returns:
                作成されたタスクのID
            """
            task = NotionTask(
                title=title, description=description, steps=steps, slack_url=slack_url
            )

            # sync関数を非同期的に実行する工夫（実際の環境では適切に変更）
            result = asyncio.run_coroutine_threadsafe(
                self.notion_service.create_task(task), asyncio.get_event_loop()
            ).result()

            return (
                f"Task created with ID: {result}" if result else "Failed to create task"
            )

        @tool("reply_to_slack")
        def reply_to_slack(
            channel: str, text: str, thread_ts: Optional[str] = None
        ) -> str:
            """
            Slackにメッセージを返信する

            Args:
                channel: チャンネルID
                text: 送信するテキスト
                thread_ts: スレッドのタイムスタンプ（オプション）

            Returns:
                送信結果
            """
            # sync関数を非同期的に実行する工夫（実際の環境では適切に変更）
            result = asyncio.run_coroutine_threadsafe(
                self.slack_service.send_message(channel, text, thread_ts),
                asyncio.get_event_loop(),
            ).result()

            return "Message sent successfully" if result else "Failed to send message"

        # ツールを登録
        self.tools = [create_notion_task, reply_to_slack]

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

            # MCPツールを使用して処理
            await self.process_with_mcp(task, result)

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

    async def process_with_mcp(
        self, task: MentionTask, analysis: TaskAnalysisResult
    ) -> None:
        """
        MCPツールを使用してタスクを処理する

        Args:
            task: 処理するタスク
            analysis: 分析結果
        """
        try:
            # ツール定義をJSON化
            tools_json = json.dumps(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    p: {
                                        "type": "string" if p != "steps" else "array",
                                        "items": {"type": "string"}
                                        if p == "steps"
                                        else None,
                                    }
                                    for p in tool.args
                                },
                                "required": [p for p in tool.args if p != "thread_ts"],
                            },
                        },
                    }
                    for tool in self.tools
                ]
            )

            # 処理用のプロンプト作成
            prompt = f"""
            以下のSlackメンションを処理し、適切なアクションを実行してください。
            
            # メンション情報
            ユーザー: {task.user}
            チャンネル: {task.channel}
            タイムスタンプ: {task.ts}
            スレッドタイムスタンプ: {task.thread_ts if task.thread_ts else "なし"}
            
            # メンション内容
            {task.text}
            
            # 分析結果
            返信内容: {analysis.content}
            フォローアップ必要: {analysis.requires_follow_up}
            
            # 指示
            1. Slackに分析結果の返信内容を送信してください。
            2. フォローアップが必要な場合は、Notionにタスクを作成してください。
            
            使用可能なツールの情報を参考にして、適切なアクションを選択してください。
            """

            # Slackへの返信を実行
            thread_ts = task.thread_ts or task.ts
            reply_result = await self.slack_service.send_message(
                channel=task.channel, text=analysis.content, thread_ts=thread_ts
            )

            logger.info(f"Slack reply result: {reply_result}")

            # Notionタスクが必要な場合
            if analysis.requires_follow_up:
                # Slackメッセージへのリンクを取得
                slack_url = (
                    self.slack_service.get_permalink(task.channel, task.ts) or ""
                )

                # タスク作成プロンプト
                task_prompt = PromptTemplate.from_template(
                    """
                    あなたは、SlackメッセージからNotionタスクを作成するAIアシスタントです。
                    
                    # メンション内容
                    {text}
                    
                    # 分析結果
                    {analysis}
                    
                    # 指示
                    以下の形式でNotionタスクの内容を生成してください：
                    
                    1. タイトル: タスクの簡潔なタイトル（80文字以内）
                    2. 説明: タスクの詳細な説明（背景、目的、問題点など）
                    3. 手順: タスク完了のための具体的なステップ（箇条書きで5つ程度）
                    
                    # 出力形式
                    ```json
                    {
                      "title": "タスクのタイトル",
                      "description": "タスクの詳細な説明",
                      "steps": [
                        "ステップ1",
                        "ステップ2",
                        "ステップ3",
                        ...
                      ]
                    }
                    ```
                    """
                )

                # LLMでタスク内容を生成
                chain = task_prompt | self.llm | StrOutputParser()
                task_json_str = await chain.ainvoke(
                    {"text": task.text, "analysis": analysis.content}
                )

                # JSON文字列をパース
                try:
                    # ```json と ``` を削除
                    json_content = (
                        task_json_str.replace("```json", "").replace("```", "").strip()
                    )
                    task_data = json.loads(json_content)

                    notion_task = NotionTask(
                        title=task_data.get("title", "無題のタスク"),
                        description=task_data.get("description", ""),
                        steps=task_data.get("steps", []),
                        slack_url=slack_url,
                    )

                    # Notionにタスクを作成
                    task_id = await self.notion_service.create_task(notion_task)
                    logger.info(f"Notion task created with ID: {task_id}")

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing task JSON: {e}")

        except Exception as e:
            logger.error(f"Error in process_with_mcp: {e}")
