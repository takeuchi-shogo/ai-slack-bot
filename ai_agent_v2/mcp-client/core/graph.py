"""
グラフ管理モジュール

LangGraphを使用したAIエージェント間の状態とフローを管理します
マルチエージェントシステムの調整と通信を担当します
"""

import logging
from enum import Enum
from typing import Dict, List, Literal, Optional, TypedDict

from agents.db_agent import DBQueryAgent
from agents.github_agent import GitHubResearchAgent
from agents.notion_agent import NotionTaskAgent
from agents.slack_agent import SlackResponseAgent
from config import ANTHROPIC_MODEL_NAME, MODEL_TEMPERATURE, get_agent_prompts
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """エージェントの種類を定義する列挙型"""

    CONTROLLER = "controller"
    DB_QUERY = "db_query"
    GITHUB_RESEARCH = "github_research"
    NOTION_TASK = "notion_task"
    SLACK_RESPONSE = "slack_response"


class QueryType(Enum):
    """クエリの種類を定義する列挙型"""

    GENERAL = "general"
    DB_QUERY = "db_query"
    CODE_ISSUE = "code_issue"
    TASK_CREATION = "task_creation"


class GraphState(TypedDict):
    """
    グラフの状態を管理するための型定義
    エージェント間で共有される情報を保持します
    """

    # 入力と現在の状態
    query: str
    query_type: str
    user_id: Optional[str]
    thread_ts: Optional[str]

    # 中間処理結果
    db_result: Optional[Dict]
    github_result: Optional[Dict]
    notion_result: Optional[Dict]

    # 最終出力
    response: Optional[str]

    # 履歴
    messages: List[Dict]


def determine_query_type(
    state: GraphState,
) -> Literal[
    "controller", "db_query", "github_research", "notion_task", "slack_response"
]:
    """
    クエリの種類を判断して、次に実行するエージェントを決定します

    Args:
        state: 現在のグラフ状態

    Returns:
        str: 次に実行するエージェントのタイプ
    """
    query_type = state.get("query_type")

    if query_type == QueryType.GENERAL.value:
        # 一般的なクエリは結果を直接返す
        return "slack_response"
    elif query_type == QueryType.DB_QUERY.value:
        # データベースクエリはDBエージェントに送る
        return "db_query"
    elif query_type == QueryType.CODE_ISSUE.value:
        # コード問題はGitHubリサーチエージェントに送る
        return "github_research"
    elif query_type == QueryType.TASK_CREATION.value:
        # タスク作成はGitHubリサーチを最初に行い、その後Notionエージェントに送る
        if not state.get("github_result"):
            return "github_research"
        elif not state.get("notion_result"):
            return "notion_task"
        return "slack_response"
    else:
        # デフォルトはSlack応答に送る
        return "slack_response"


def determine_next_after_github(
    state: GraphState,
) -> Literal["notion_task", "slack_response"]:
    """
    GitHubリサーチ後の次のステップを決定

    Args:
        state: 現在のグラフ状態

    Returns:
        str: 次に実行するエージェントのタイプ
    """
    query_type = state.get("query_type")

    if query_type == QueryType.TASK_CREATION.value:
        return "notion_task"
    else:
        return "slack_response"


def determine_next_after_db(state: GraphState) -> Literal["slack_response"]:
    """
    DBクエリ後の次のステップを決定

    Args:
        state: 現在のグラフ状態

    Returns:
        str: 次に実行するエージェントのタイプ
    """
    return "slack_response"


def determine_next_after_notion(state: GraphState) -> Literal["slack_response"]:
    """
    Notionタスク作成後の次のステップを決定

    Args:
        state: 現在のグラフ状態

    Returns:
        str: 次に実行するエージェントのタイプ
    """
    return "slack_response"


class GraphManager:
    """
    LangGraphを使用したAIエージェントグラフを管理するクラス

    複数のエージェント間の通信と状態遷移を管理します。
    エージェントの役割:
    - Controller: クエリの種類を判断し、適切なエージェントに割り当て
    - DB Query: データベースへのクエリを実行
    - GitHub Research: GitHubからコード情報を取得して分析
    - Notion Task: Notionにタスクを作成
    - Slack Response: 結果をSlackに送信
    """

    def __init__(
        self, model_provider="anthropic", tool_manager=None, db_connection=None
    ):
        """
        GraphManagerの初期化

        Args:
            model_provider: 使用するモデルプロバイダー (デフォルト: "anthropic")
            tool_manager: ツール管理クラスのインスタンス
            db_connection: データベース接続のインスタンス
        """
        self.model_provider = model_provider
        self.tool_manager = tool_manager
        self.db_connection = db_connection

        # LLMの初期化
        self.llm = ChatAnthropic(
            model=ANTHROPIC_MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            anthropic_api_key=None,  # 環境変数から自動読み込み
        )

        # エージェントの初期化
        self.agents = {}
        self.db_agent = None
        self.github_agent = None
        self.notion_agent = None
        self.slack_agent = None

        # グラフの初期化
        self.graph = None

    def _create_controller_agent(self):
        """コントローラーエージェントを作成"""
        prompts = get_agent_prompts()

        async def controller_agent(state: GraphState) -> Dict:
            """ユーザークエリを分析し、適切なエージェントに割り当てるコントローラーエージェント"""
            query = state["query"]

            # コントローラープロンプトを作成
            controller_prompt = prompts["controller"]
            messages = [
                SystemMessage(content=controller_prompt),
                HumanMessage(
                    content=f"ユーザークエリ: {query}\n\nこのクエリの種類を判断し、適切なカテゴリに分類してください。"
                ),
            ]

            # LLMに問い合わせ
            response = self.llm.invoke(messages)
            response_text = response.content

            # レスポンスからクエリタイプを抽出（シンプルな実装）
            query_type = QueryType.GENERAL.value  # デフォルト

            if (
                "データベース" in response_text.lower()
                or "sql" in response_text.lower()
                or "クエリ" in response_text.lower()
            ):
                query_type = QueryType.DB_QUERY.value
            elif (
                "github" in response_text.lower()
                or "コード" in response_text.lower()
                or "バグ" in response_text.lower()
            ):
                if (
                    "タスク" in response_text.lower()
                    or "notion" in response_text.lower()
                ):
                    query_type = QueryType.TASK_CREATION.value
                else:
                    query_type = QueryType.CODE_ISSUE.value

            logger.info(f"クエリタイプ判定: {query_type}")

            # 状態を更新
            return {"query_type": query_type}

        return controller_agent

    async def initialize_agents(self):
        """すべてのエージェントを初期化"""
        # コントローラーエージェント
        self.agents[AgentType.CONTROLLER.value] = self._create_controller_agent()

        # DBクエリエージェント
        self.db_agent = DBQueryAgent(llm=self.llm, db_connection=self.db_connection)
        await self.db_agent.initialize()
        self.agents[AgentType.DB_QUERY.value] = self.db_agent.process

        # GitHubリサーチエージェント
        self.github_agent = GitHubResearchAgent(
            llm=self.llm, tool_manager=self.tool_manager
        )
        self.agents[AgentType.GITHUB_RESEARCH.value] = self.github_agent.process

        # Notionタスクエージェント
        self.notion_agent = NotionTaskAgent(
            llm=self.llm, tool_manager=self.tool_manager
        )
        self.agents[AgentType.NOTION_TASK.value] = self.notion_agent.process

        # Slack応答エージェント
        self.slack_agent = SlackResponseAgent(
            llm=self.llm, tool_manager=self.tool_manager
        )
        self.agents[AgentType.SLACK_RESPONSE.value] = self.slack_agent.process

        logger.info("すべてのエージェントが初期化されました")

    async def build_graph(self):
        """
        エージェントグラフを構築

        LangGraphを使用してエージェント間の通信フローを定義します

        Returns:
            StateGraph: コンパイル済みのエージェントグラフ
        """
        # エージェントが初期化されていない場合は初期化
        if not self.agents:
            await self.initialize_agents()

        # グラフを構築するための基本フレームワーク
        builder = StateGraph(GraphState)

        # ノードの追加
        for agent_type, agent_func in self.agents.items():
            builder.add_node(agent_type, agent_func)

        # エッジの定義
        # 1. コントローラーからの分岐
        builder.add_conditional_edges(
            AgentType.CONTROLLER.value,
            determine_query_type,
            {
                AgentType.DB_QUERY.value: AgentType.DB_QUERY.value,
                AgentType.GITHUB_RESEARCH.value: AgentType.GITHUB_RESEARCH.value,
                AgentType.NOTION_TASK.value: AgentType.NOTION_TASK.value,
                AgentType.SLACK_RESPONSE.value: AgentType.SLACK_RESPONSE.value,
            },
        )

        # 2. GitHubリサーチ後の分岐
        builder.add_conditional_edges(
            AgentType.GITHUB_RESEARCH.value,
            determine_next_after_github,
            {
                AgentType.NOTION_TASK.value: AgentType.NOTION_TASK.value,
                AgentType.SLACK_RESPONSE.value: AgentType.SLACK_RESPONSE.value,
            },
        )

        # 3. DBクエリ後の分岐
        builder.add_conditional_edges(
            AgentType.DB_QUERY.value,
            determine_next_after_db,
            {AgentType.SLACK_RESPONSE.value: AgentType.SLACK_RESPONSE.value},
        )

        # 4. Notionタスク作成後の分岐
        builder.add_conditional_edges(
            AgentType.NOTION_TASK.value,
            determine_next_after_notion,
            {AgentType.SLACK_RESPONSE.value: AgentType.SLACK_RESPONSE.value},
        )

        # 5. Slack応答は終了
        builder.add_edge(AgentType.SLACK_RESPONSE.value, END)

        # グラフをコンパイル
        self.graph = builder.compile()
        return self.graph

    async def process_query(
        self, query: str, user_id: Optional[str] = None, thread_ts: Optional[str] = None
    ) -> Dict:
        """
        ユーザークエリを処理

        Args:
            query: ユーザーからのクエリ
            user_id: ユーザーID（オプション）
            thread_ts: スレッドタイムスタンプ（オプション）

        Returns:
            Dict: 処理結果
        """
        # グラフが初期化されていない場合は構築
        if not self.graph:
            await self.build_graph()

        # 初期状態を設定
        initial_state = {
            "query": query,
            "query_type": "",  # コントローラーで設定される
            "user_id": user_id,
            "thread_ts": thread_ts,
            "db_result": None,
            "github_result": None,
            "notion_result": None,
            "response": None,
            "messages": [],
        }

        # グラフを実行
        try:
            logger.info(f"クエリ処理開始: {query}")
            result = await self.graph.ainvoke(initial_state)
            logger.info("グラフ実行完了")
            return result
        except Exception as e:
            logger.error(f"グラフ実行エラー: {e}")
            return {
                "query": query,
                "error": str(e),
                "response": f"エラーが発生しました: {str(e)}",
            }

    async def cleanup(self):
        """リソースのクリーンアップ"""
        if self.db_agent:
            await self.db_agent.cleanup()

        logger.info("グラフマネージャーのリソースをクリーンアップしました")
