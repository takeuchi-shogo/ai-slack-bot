import json
import logging
from typing import Any, Dict, TypedDict

from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_anthropic import ChatAnthropicMessages
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from ..models import MentionTask, NotionTask, TaskAnalysisResult
from ..services.notion_service import NotionService
from ..services.slack_service import SlackService

logger = logging.getLogger(__name__)


# LangGraph用の状態定義
class AgentState(TypedDict):
    task: MentionTask
    analysis: TaskAnalysisResult
    slack_response: str
    notion_task: NotionTask
    error: str
    final_result: Dict[str, Any]


# MCPサーバーで実行するLLMグラフ
class MCPServer:
    """MCP サーバー"""

    def __init__(self):
        self.slack_service = SlackService()
        self.notion_service = NotionService()

        # LLMの初期化
        self.claude = ChatAnthropicMessages(
            model="claude-3-opus-20240229", temperature=0.2
        )

        self.gpt4 = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.2)

        # LangGraphの構築
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraphを構築する"""

        # 初期状態のグラフ
        builder = StateGraph(AgentState)

        # ノードの追加
        builder.add_node("analyze_intent", self.analyze_intent)
        builder.add_node("generate_slack_response", self.generate_slack_response)
        builder.add_node("evaluate_notion_need", self.evaluate_notion_need)
        builder.add_node("create_notion_task", self.create_notion_task)
        builder.add_node("send_slack_response", self.send_slack_response)

        # エッジの追加
        builder.add_edge("analyze_intent", "generate_slack_response")
        builder.add_edge("generate_slack_response", "evaluate_notion_need")

        # 条件付きエッジ
        builder.add_conditional_edges(
            "evaluate_notion_need",
            self.needs_notion_task,
            {True: "create_notion_task", False: "send_slack_response"},
        )

        builder.add_edge("create_notion_task", "send_slack_response")
        builder.add_edge("send_slack_response", END)

        # スタートノードを設定
        builder.set_entry_point("analyze_intent")

        return builder.compile()

    async def analyze_intent(self, state: AgentState) -> AgentState:
        """メッセージの意図を分析する"""
        try:
            task = state["task"]

            # 分析用プロンプト
            prompt = ChatPromptTemplate.from_template(
                """
                あなたは、Slackのメッセージを分析するAIアシスタントです。
                以下のSlackメンションの内容を分析し、メッセージの意図を理解してください。
                
                # メンション内容
                {text}
                
                # 分析すべき点
                1. メッセージはどのような意図を持っていますか？（質問、要求、報告など）
                2. メッセージのトピックは何ですか？
                3. メッセージの緊急性はどの程度ですか？
                4. メッセージへの対応にはどのような専門知識が必要ですか？
                
                # 回答形式
                分析結果の要約を簡潔に記述してください。
                """
            )

            # LLMで分析を実行
            chain = prompt | self.claude | StrOutputParser()
            analysis_result = await chain.ainvoke({"text": task.text})

            # 分析結果を記録
            return {
                **state,
                "analysis": TaskAnalysisResult(
                    content=analysis_result,
                    requires_follow_up=False,  # この時点では不明なので仮の値
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_intent: {e}")
            return {
                **state,
                "error": f"Intent analysis failed: {str(e)}",
                "analysis": TaskAnalysisResult(
                    content="分析中にエラーが発生しました", requires_follow_up=False
                ),
            }

    async def generate_slack_response(self, state: AgentState) -> AgentState:
        """Slack用の応答を生成する"""
        try:
            task = state["task"]
            analysis = state["analysis"]

            # 応答生成プロンプト
            prompt = PromptTemplate.from_template(
                """
                あなたはSlackボットとして、以下のメンションに対する返答を生成します。
                
                # メンション内容
                {text}
                
                # 分析結果
                {analysis}
                
                # 指示
                1. ユーザーのメンションに対して、適切かつ簡潔な返答を生成してください
                2. 返答は丁寧で親しみやすい口調で、かつ専門的な知識を反映させてください
                3. 回答は200文字以内に収めてください
                4. ユーザー名は <@{user}> の形式で言及してください
                
                回答をそのまま出力してください。プロンプトの内容をそのまま含めないでください。
                """
            )

            # LLMで応答を生成
            chain = prompt | self.gpt4 | StrOutputParser()
            response = await chain.ainvoke(
                {"text": task.text, "analysis": analysis.content, "user": task.user}
            )

            # 応答を記録
            return {**state, "slack_response": response}

        except Exception as e:
            logger.error(f"Error in generate_slack_response: {e}")
            return {
                **state,
                "error": f"Response generation failed: {str(e)}",
                "slack_response": f"<@{task.user}> すみません、応答の生成中にエラーが発生しました。",
            }

    async def evaluate_notion_need(self, state: AgentState) -> AgentState:
        """Notionタスクの必要性を評価する"""
        try:
            task = state["task"]
            analysis = state["analysis"]

            # 評価プロンプト
            prompt = PromptTemplate.from_template(
                """
                あなたは、メッセージを分析してNotionでのタスク作成が必要かどうかを判断するAIアシスタントです。
                
                # メンション内容
                {text}
                
                # 分析結果
                {analysis}
                
                # 判断基準
                以下のような場合、Notionタスクが必要と判断してください：
                1. バグ修正や機能追加などの具体的な開発タスクが必要な場合
                2. 詳細な調査や分析が必要な問題提起がある場合
                3. 複数人での対応や長期的な対応が必要な課題がある場合
                4. 後で参照する必要がある重要な情報やリクエストがある場合
                
                # 回答形式
                NotionタスクとしてトラッキングすべきかどうかをTrue/Falseで出力してください。
                理由も簡潔に説明してください。
                
                出力例：
                ```
                要フォローアップ: True
                理由: バグ修正が必要なため、詳細な調査と対応をトラッキングする必要があります。
                ```
                """
            )

            # LLMで評価を実行
            chain = prompt | self.claude | StrOutputParser()
            evaluation = await chain.ainvoke(
                {"text": task.text, "analysis": analysis.content}
            )

            # 評価結果のパース
            lines = evaluation.strip().split("\n")
            requires_follow_up = False
            reason = ""

            for line in lines:
                if line.startswith("要フォローアップ:"):
                    follow_up_text = (
                        line.replace("要フォローアップ:", "").strip().lower()
                    )
                    requires_follow_up = follow_up_text == "true"
                elif line.startswith("理由:"):
                    reason = line.replace("理由:", "").strip()

            # 分析結果を更新
            updated_analysis = TaskAnalysisResult(
                content=analysis.content, requires_follow_up=requires_follow_up
            )

            return {**state, "analysis": updated_analysis}

        except Exception as e:
            logger.error(f"Error in evaluate_notion_need: {e}")
            return {
                **state,
                "error": f"Notion need evaluation failed: {str(e)}",
                "analysis": TaskAnalysisResult(
                    content=state["analysis"].content, requires_follow_up=False
                ),
            }

    async def create_notion_task(self, state: AgentState) -> AgentState:
        """Notionタスクを作成する"""
        try:
            task = state["task"]
            analysis = state["analysis"]

            # Slackメッセージへのリンクを取得
            slack_url = self.slack_service.get_permalink(task.channel, task.ts) or ""

            # タスク作成プロンプト
            prompt = PromptTemplate.from_template(
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
            chain = prompt | self.claude | StrOutputParser()
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

                return {**state, "notion_task": notion_task}

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing task JSON: {e}")
                # JSONのパースに失敗した場合のフォールバック
                notion_task = NotionTask(
                    title="Slackメッセージから生成したタスク",
                    description=task.text,
                    steps=["タスクの詳細を確認して必要な手順を作成してください"],
                    slack_url=slack_url,
                )

                # Notionにタスクを作成
                task_id = await self.notion_service.create_task(notion_task)

                return {
                    **state,
                    "notion_task": notion_task,
                    "error": f"Task JSON parsing failed: {str(e)}",
                }

        except Exception as e:
            logger.error(f"Error in create_notion_task: {e}")
            return {**state, "error": f"Notion task creation failed: {str(e)}"}

    async def send_slack_response(self, state: AgentState) -> AgentState:
        """Slackに応答を送信する"""
        try:
            task = state["task"]
            response = state["slack_response"]

            # Notionタスクを作成した場合はその情報も追加
            if state["analysis"].requires_follow_up and "notion_task" in state:
                notion_task = state["notion_task"]
                response += f"\n\nNotionにタスクを作成しました: {notion_task.title}"

            # Slackに応答を送信
            thread_ts = task.thread_ts or task.ts
            success = await self.slack_service.send_message(
                channel=task.channel, text=response, thread_ts=thread_ts
            )

            result = {
                "task_id": task.id,
                "success": success,
                "slack_response_sent": success,
                "notion_task_created": state["analysis"].requires_follow_up
                and "notion_task" in state,
            }

            if "error" in state and state["error"]:
                result["error"] = state["error"]

            return {**state, "final_result": result}

        except Exception as e:
            logger.error(f"Error in send_slack_response: {e}")
            return {
                **state,
                "error": f"Slack response sending failed: {str(e)}",
                "final_result": {
                    "task_id": state["task"].id,
                    "success": False,
                    "error": str(e),
                },
            }

    def needs_notion_task(self, state: AgentState) -> bool:
        """Notionタスクが必要かどうかを判断する"""
        return state["analysis"].requires_follow_up

    async def process(self, task: MentionTask) -> Dict[str, Any]:
        """
        タスクを処理する

        Args:
            task: 処理するタスク

        Returns:
            処理結果
        """
        # 初期状態
        initial_state = AgentState(
            task=task,
            analysis=TaskAnalysisResult(content="", requires_follow_up=False),
            slack_response="",
            notion_task=NotionTask(title="", description="", steps=[], slack_url=""),
            error="",
            final_result={},
        )

        # グラフを実行
        result = await self.graph.ainvoke(initial_state)

        return result["final_result"]
