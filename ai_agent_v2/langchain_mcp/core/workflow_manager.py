import asyncio
import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from core.query_router import QueryRouter
from core.slack_agent import SlackAgent

logger = logging.getLogger(__name__)


class WorkflowManager:
    """エージェント間のワークフローを管理し、複雑なタスクを実行するクラス"""

    def __init__(self):
        self.query_router = QueryRouter()
        self.slack_agent = SlackAgent()

    async def process_request(
        self, query: str, channel_id: str = None, thread_ts: str = None
    ) -> Dict[str, Any]:
        """ユーザーリクエストを処理し、適切なエージェントにルーティングする

        Args:
            query: ユーザーからのクエリ
            channel_id: Slackチャンネルのid
            thread_ts: Slackスレッドのts

        Returns:
            処理結果
        """
        # クエリを分析
        analysis = await self.query_router.analyze_query(query)
        logger.info(f"クエリ分析結果: {analysis}")

        # エージェントにルーティングして処理
        response = await self.query_router.route_to_agent(analysis, query)

        # Slackに応答を送信（必要な場合）
        if channel_id and response:
            await self.slack_agent.send_response(
                channel_id=channel_id,
                text=response.get("response", "処理が完了しました"),
                thread_ts=thread_ts,
            )

        return response

    def create_workflow_graph(self) -> StateGraph:
        """複数エージェント間の連携ワークフローをグラフとして定義する

        ユーザークエリ → 分析 → 適切なエージェント → Slack応答
                            └→ Notionタスク作成（必要な場合）

        Returns:
            LangGraph StateGraph インスタンス
        """

        # ワークフローの各ステップを定義する関数
        def analyze_query(state):
            query = state["query"]
            analysis_future = asyncio.ensure_future(
                self.query_router.analyze_query(query)
            )
            asyncio.get_event_loop().run_until_complete(analysis_future)
            analysis = analysis_future.result()

            return {"analysis": analysis, **state}

        def route_to_agent(state):
            analysis = state["analysis"]
            query = state["query"]

            route_future = asyncio.ensure_future(
                self.query_router.route_to_agent(analysis, query)
            )
            asyncio.get_event_loop().run_until_complete(route_future)
            agent_response = route_future.result()

            return {"agent_response": agent_response, **state}

        def create_notion_task(state):
            # Notion タスク作成の処理（必要な場合）
            analysis = state["analysis"]

            if analysis.get("create_task", False):
                # Notionタスク作成の実装
                pass

            return state

        def send_slack_response(state):
            agent_response = state["agent_response"]
            channel_id = state.get("channel_id")
            thread_ts = state.get("thread_ts")

            if channel_id:
                response_text = agent_response.get("response", "処理が完了しました")
                response_future = asyncio.ensure_future(
                    self.slack_agent.send_response(channel_id, response_text, thread_ts)
                )
                asyncio.get_event_loop().run_until_complete(response_future)

            return {"status": "complete", **state}

        # ワークフローグラフの定義
        workflow = StateGraph(state_schema={"query": str})

        # ノードの追加
        workflow.add_node("analyze_query", analyze_query)
        workflow.add_node("route_to_agent", route_to_agent)
        workflow.add_node("create_notion_task", create_notion_task)
        workflow.add_node("send_slack_response", send_slack_response)

        # エッジの追加
        workflow.add_edge("analyze_query", "route_to_agent")
        workflow.add_edge("route_to_agent", "create_notion_task")
        workflow.add_edge("create_notion_task", "send_slack_response")
        workflow.add_edge("send_slack_response", END)

        # スタートノードの設定
        workflow.set_entry_point("analyze_query")

        return workflow.compile()
