import logging

from client.agent import AgentClient

logger = logging.getLogger(__name__)


def main():
    logger.info("Hello from agents!")
    client = AgentClient()
    query = """
    ユーザーからのクエリ
    
    ログインに問題がありました。
    調べてください。
    """
    client.run(query)


if __name__ == "__main__":
    main()
