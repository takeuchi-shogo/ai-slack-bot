import logging

from agent.state import State
from agent.workflow_manager import WorkflowManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentClient:
    def __init__(self):
        self.workflow_manager = WorkflowManager()

    def run(self, query: str):
        logger.info(f"Running workflow with query: {query}")
        graph = self.workflow_manager.create_workflow_graph()
        state = State(query=query)
        for event in graph.stream(state):
            logger.info(event)
