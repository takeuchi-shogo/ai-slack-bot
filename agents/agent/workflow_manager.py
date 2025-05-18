import asyncio
import logging
from typing import Any, Dict

from agent.code_review import CodeReviewAgent
from agent.database import DatabaseAgent
from agent.log import LogAgent
from agent.state import Message, State
from agent.user_proxy import UserProxyAgent
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


class WorkflowManager:
    """エージェント間のワークフローを管理し、複雑なタスクを実行するクラス"""

    def __init__(self):
        self.user_proxy_agent = UserProxyAgent()
        self.database_agent = DatabaseAgent()
        self.log_agent = LogAgent()
        self.code_review_agent = CodeReviewAgent()

    async def process_request(
        self, query: str, channel_id: str = None, thread_ts: str = None
    ) -> Dict[str, Any]:
        """ユーザーリクエストを処理し、適切なエージェントにルーティングする

        Args:
            query: ユーザーからのクエリ
            channel_id: Slackチャンネルのid
            thread_ts: Slackスレッドのts
        """
        pass

    def create_workflow_graph(self) -> StateGraph:
        """
        ワークフローの各ステップを定義する関数

        Returns:
            StateGraph: ワークフローのグラフ
        """

        # ワークフローの各ステップを定義する関数
        def analyze_query(state: State):
            """
            ユーザーのクエリを分析し、データの取得が必要かどうかを判断する
            シンプルなクエリの場合は、データの取得は不要
            データの取得が必要な場合は、DB検索、ログ検索を並行して行う
            """
            user_proxy_agent = UserProxyAgent()
            agent_response = asyncio.run(user_proxy_agent.execute(state.query))
            logger.info(f"analyze_query: {agent_response}")
            state.messages.append(
                Message(agent_name="user_proxy", message=agent_response["content"])
            )
            state.is_need_data = agent_response["is_need_data"]
            return state

        def need_search_data(state: State):
            """
            データの取得が必須なので、DB検索、ログ検索を並行して行う
            """
            pass

        def review_github_code(state: State):
            """
            コードレビューを行う
            """
            pass

        def slack_response(state: State):
            """
            必要によってNotionにタスクを作成する
            Slackに応答を返す
            """
            pass

        # ワークフローのグラフを定義
        workflow = StateGraph(state_schema=State)

        # スタート
        workflow.add_edge(START, "analyze_query")

        # ワークフローの各ノードを定義
        workflow.add_node("analyze_query", analyze_query)
        workflow.add_node("need_search_data", need_search_data)
        workflow.add_node("review_github_code", review_github_code)
        workflow.add_node("slack_response", slack_response)

        # 1.条件分岐エッジの追加
        workflow.add_conditional_edges(
            "analyze_query",
            lambda state: getattr(state, "is_need_data", False),
            {
                True: "need_search_data",
                False: "slack_response",
            },
        )

        # 2.条件分岐エッジの追加
        workflow.add_conditional_edges(
            "need_search_data",
            lambda state: getattr(state, "is_need_code_review", False),
            {
                True: "review_github_code",
                False: "slack_response",
            },
        )

        # 3.Slack応答後のエッジの追加
        workflow.add_edge("slack_response", END)

        return workflow.compile()
        return workflow.compile()
