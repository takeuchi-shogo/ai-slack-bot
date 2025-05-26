import logging

from agent.state import State
from agent.workflow_manager import WorkflowManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentClient:
    def __init__(self):
        logger.info("AgentClient初期化開始")
        self.workflow_manager = WorkflowManager()
        logger.info("AgentClient初期化完了")

    async def run(self, query: str, channel_id: str = None, thread_ts: str = None):
        """非同期でワークフローを実行"""
        logger.info(f"Running workflow with query: {query}")
        try:
            logger.info("ワークフローグラフ作成開始")
            graph = self.workflow_manager.create_workflow_graph()
            logger.info("ワークフローグラフ作成完了")

            logger.info("State初期化開始")
            state = State(query=query)

            # channel_idとthread_tsが提供された場合は設定
            if channel_id:
                state.channel_id = channel_id
            if thread_ts:
                state.thread_ts = thread_ts
            logger.info("State初期化完了")

            logger.info("ワークフロー実行開始（非同期版）")
            # 非同期ストリーミングを使用
            async for event in graph.astream(state):
                logger.info(f"ワークフローイベント: {event}")

        except Exception as e:
            logger.error(
                f"ワークフロー実行中にエラーが発生しました: {type(e).__name__}: {e}"
            )
            import traceback

            logger.error(f"スタックトレース: {traceback.format_exc()}")
            raise
        finally:
            # リソースのクリーンアップ
            await self._cleanup()

    async def _cleanup(self):
        """リソースのクリーンアップ"""
        try:
            logger.info("クリーンアップ開始")
            # WorkflowManagerが持つエージェントのクリーンアップ
            if hasattr(self.workflow_manager, "user_proxy_agent"):
                if hasattr(self.workflow_manager.user_proxy_agent, "model_handler"):
                    if hasattr(
                        self.workflow_manager.user_proxy_agent.model_handler, "aclose"
                    ):
                        await self.workflow_manager.user_proxy_agent.model_handler.aclose()

            logger.info("AgentClientのクリーンアップが完了しました")
        except Exception as e:
            logger.warning(f"クリーンアップ中にエラーが発生しました: {e}")
