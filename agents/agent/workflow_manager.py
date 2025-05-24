import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from agent.database import DatabaseAgent
from agent.log import LogAgent
from agent.slack import SlackAgent
from agent.state import Message, State
from agent.user_proxy import UserProxyAgent

logger = logging.getLogger(__name__)


class WorkflowManager:
    """エージェント間のワークフローを管理し、複雑なタスクを実行するクラス"""

    def __init__(self):
        self.user_proxy_agent = UserProxyAgent()
        self.database_agent = DatabaseAgent()
        self.log_agent = LogAgent()
        # self.code_review_agent = CodeReviewAgent()

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
        async def analyze_query(state: State):
            """
            ユーザーのクエリを分析し、データの取得が必要かどうかを判断する
            シンプルなクエリの場合は、データの取得は不要
            データの取得が必要な場合は、DB検索、ログ検索を並行して行う
            """
            try:
                user_proxy_agent = UserProxyAgent()
                agent_response = await user_proxy_agent.execute(state.query)
                logger.info(f"analyze_query: {agent_response}")

                # エラーハンドリング対応
                if agent_response.get("error_occurred"):
                    state.messages.append(
                        Message(
                            agent_name="error_handler",
                            message=HumanMessage(content=agent_response["content"]),
                        )
                    )
                    state.is_need_data = agent_response.get("is_need_data", False)
                else:
                    state.messages.append(
                        Message(
                            agent_name="user_proxy",
                            message=HumanMessage(content=agent_response["content"]),
                        )
                    )
                    state.is_need_data = agent_response["is_need_data"]
            except Exception as e:
                logger.error(f"analyze_query error: {type(e).__name__}: {str(e)}")
                state.messages.append(
                    Message(
                        agent_name="error_handler",
                        message=HumanMessage(
                            content=f"クエリ分析中にエラーが発生しました: {str(e)}"
                        ),
                    )
                )
                state.is_need_data = False
            return state

        async def generate_sql(state: State):
            """
            自然言語クエリからSQLを生成する
            """
            try:
                database_agent = DatabaseAgent()
                # SQLクエリを生成（実行はしない）
                generated_sql = await database_agent.process_create_sql(
                    state.query, state
                )
                logger.info(f"generate_sql: {generated_sql}")

                if generated_sql:
                    state.generated_sql = generated_sql
                    state.messages.append(
                        Message(
                            agent_name="database_generator",
                            message=HumanMessage(
                                content=f"以下のSQLクエリを生成しました：\n\n```sql\n{generated_sql}\n```"
                            ),
                        )
                    )
                else:
                    state.messages.append(
                        Message(
                            agent_name="database_generator",
                            message=HumanMessage(
                                content="SQLクエリの生成に失敗しました。"
                            ),
                        )
                    )
                    state.sql_confirmation_needed = False  # エラーの場合は確認不要
            except Exception as e:
                logger.error(f"generate_sql error: {type(e).__name__}: {str(e)}")
                state.messages.append(
                    Message(
                        agent_name="database_generator",
                        message=HumanMessage(
                            content=f"SQL生成中にエラーが発生しました: {str(e)}"
                        ),
                    )
                )
                state.sql_confirmation_needed = False
            return state

        def confirm_sql(state: State):
            """
            生成されたSQLをユーザーに確認してもらう (Human in the Loop)
            """
            if not state.generated_sql:
                logger.warning("confirm_sql: 生成されたSQLがありません")
                state.sql_confirmed = False
                return state

            # TODO: ここで実際のHuman in the Loop実装
            # 現在は仮実装として自動承認
            # 実際の実装では以下のような方法が考えられます：
            # 1. Slackにメッセージを送信してボタンで確認
            # 2. Web UIで確認画面を表示
            # 3. メール通知で確認

            confirmation_message = f"""
生成されたSQLクエリを確認してください：

```sql
{state.generated_sql}
```

このSQLクエリを実行してもよろしいですか？
- 承認する場合：「承認」または「OK」と入力
- 修正が必要な場合：「修正」と修正内容を入力
- 拒否する場合：「拒否」または「NG」と入力
"""

            state.messages.append(
                Message(
                    agent_name="sql_confirmer",
                    message=HumanMessage(content=confirmation_message),
                )
            )

            # 仮実装：自動承認（実際の実装では外部入力を待つ）
            # TODO: 実際のHuman in the Loop実装に置き換える
            logger.info("confirm_sql: 仮実装として自動承認しています")
            state.sql_confirmed = True
            state.sql_confirmation_response = "自動承認（仮実装）"

            return state

        async def execute_sql(state: State):
            """
            確認されたSQLクエリを実行してデータを取得する
            """
            if not state.sql_confirmed:
                logger.warning("execute_sql: SQLが確認されていません")
                state.messages.append(
                    Message(
                        agent_name="database_executor",
                        message=HumanMessage(
                            content="SQLクエリが確認されていないため、実行をスキップします。"
                        ),
                    )
                )
                return state

            if not state.generated_sql:
                logger.warning("execute_sql: 実行するSQLがありません")
                return state

            # 確認されたSQLを実際のsql_queryフィールドに設定
            state.sql_query = state.generated_sql

            try:
                database_agent = DatabaseAgent()
                agent_response = await database_agent.execute(state.query, state)
                logger.info(f"execute_sql: {agent_response}")

                state.messages.append(
                    Message(
                        agent_name="database_executor",
                        message=HumanMessage(content=agent_response["response"]),
                    )
                )
                state.database_result = agent_response.get("result", "")
            except Exception as e:
                logger.error(f"execute_sql error: {type(e).__name__}: {str(e)}")
                state.messages.append(
                    Message(
                        agent_name="database_executor",
                        message=HumanMessage(
                            content=f"SQL実行中にエラーが発生しました: {str(e)}"
                        ),
                    )
                )
            return state

        def review_github_code(state: State):
            """
            コードレビューを行う
            """
            state.code_review_result = "テストコードレビュー結果"
            return state

        async def slack_response(state: State):
            """
            必要によってNotionにタスクを作成する
            Slackに応答を返す
            """
            try:
                slack_agent = SlackAgent()
                # channel_idがStateに存在しない、または空文字列の場合はデフォルト値を使用
                channel_id = getattr(state, "channel_id", "") or "C062T1JP41M"
                # thread_tsがStateに存在しない、または空文字列の場合はデフォルト値を使用
                thread_ts = getattr(state, "thread_ts", "") or ""
                # messagesの最後のcontentを安全に取得
                last_message_content = (
                    state.messages[-1].message.content
                    if state.messages
                    else "処理が完了しました。"
                )

                logger.info(
                    f"slack_response: channel_id='{channel_id}', thread_ts='{thread_ts}'"
                )

                # channel_idをリスト形式に変換して呼び出し
                agent_response = await slack_agent.send_message(
                    [channel_id], last_message_content, thread_ts
                )
                logger.info(f"slack_response: {agent_response}")
                state.messages.append(
                    Message(
                        agent_name="slack_response",
                        message=HumanMessage(content=agent_response["content"]),
                    )
                )
            except Exception as e:
                logger.error(f"slack_response error: {type(e).__name__}: {str(e)}")
                # エラー時は処理を継続
                error_message = f"Slack送信エラー: {str(e)}"
                state.messages.append(
                    Message(
                        agent_name="slack_error",
                        message=HumanMessage(content=error_message),
                    )
                )
            return state

        # ワークフローのグラフを定義
        workflow = StateGraph(state_schema=State)

        # スタート
        workflow.add_edge(START, "analyze_query")

        # ワークフローの各ノードを定義
        workflow.add_node("analyze_query", analyze_query)
        workflow.add_node("generate_sql", generate_sql)
        workflow.add_node("confirm_sql", confirm_sql)
        workflow.add_node("execute_sql", execute_sql)
        workflow.add_node("review_github_code", review_github_code)
        workflow.add_node("slack_response", slack_response)

        # 1. analyze_query → generate_sql または slack_response
        workflow.add_conditional_edges(
            "analyze_query",
            lambda state: getattr(state, "is_need_data", False),
            {
                True: "generate_sql",
                False: "slack_response",
            },
        )

        # 2. generate_sql → confirm_sql または slack_response
        workflow.add_conditional_edges(
            "generate_sql",
            lambda state: getattr(state, "sql_confirmation_needed", False)
            and bool(getattr(state, "generated_sql", "")),
            {
                True: "confirm_sql",
                False: "slack_response",  # SQLが生成されなかった場合はslack_responseへ
            },
        )

        # 3. confirm_sql → execute_sql または slack_response
        workflow.add_conditional_edges(
            "confirm_sql",
            lambda state: getattr(state, "sql_confirmed", False),
            {
                True: "execute_sql",
                False: "slack_response",  # 確認が拒否された場合はslack_responseへ
            },
        )

        # 4. execute_sql → review_github_code または slack_response
        workflow.add_conditional_edges(
            "execute_sql",
            lambda state: getattr(state, "is_need_code_review", False),
            {
                True: "review_github_code",
                False: "slack_response",
            },
        )

        # 5. review_github_code → slack_response
        workflow.add_edge("review_github_code", "slack_response")

        # 6. slack_response → END
        workflow.add_edge("slack_response", END)

        return workflow.compile()
