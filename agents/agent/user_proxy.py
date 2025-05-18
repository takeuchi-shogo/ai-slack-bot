from typing import Any, Dict

from models.open_ai import OpenAIModelHandler


class UserProxyAgent:
    """
    ユーザーからのクエリを分析し、必要なエージェントとアクションを決定する
    """

    def __init__(self):
        self.model_handler = OpenAIModelHandler()
        self.controller_config = None

    async def execute(self, query: str) -> Dict[str, Any]:
        """ユーザークエリを分析し、必要なエージェントとアクションを決定する

        Args:
            query (str): ユーザーからのクエリ文字列

        Returns:
            Dict[str, Any]: 分析結果（エージェントタイプ、アクション、パラメータなど）
        """
        # プロンプトを作成
        prompt = f"""
        以下のユーザークエリを分析し、必要な対応を判断してください：
        
        ユーザークエリ：
        {query}
        
        分析結果：
        """

        # LLMに直接プロンプトを送信
        response = await self.model_handler.llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": "あなたはユーザークエリを分析し、適切な対応方法を提案するアシスタントです。",
                },
                {"role": "user", "content": prompt},
            ]
        )

        # 応答結果を辞書形式に整形
        result = {
            "content": response.content,
            "is_need_data": "データベース" in response.content
            or "ログ" in response.content,
        }

        return result
