import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from models.anthropic import AnthropicModelHandler

logger = logging.getLogger(__name__)


class AlignmentAgent:
    """応答の調整と整形を行うエージェント"""

    def __init__(self):
        self.model_handler = AnthropicModelHandler()

    async def align_response(
        self, original_response: str, context: Dict[str, Any] = None
    ) -> str:
        """応答を整形し、Slackの文脈に合わせる

        Args:
            original_response: 元の応答テキスト
            context: コンテキスト情報（チャンネル、ユーザー情報など）

        Returns:
            整形された応答テキスト
        """
        # 応答が長すぎる場合は要約
        if len(original_response) > 4000:
            return await self.summarize_response(original_response)

        # コードブロックの適切な整形
        response = self._format_code_blocks(original_response)

        # メンションの整形
        if context and "mentions" in context:
            response = self._format_mentions(response, context["mentions"])

        return response

    async def summarize_response(self, long_response: str) -> str:
        """長い応答を要約する

        Args:
            long_response: 長い応答テキスト

        Returns:
            要約された応答テキスト
        """
        system_prompt = """
        あなたは長文のテキストを簡潔に要約するスペシャリストです。
        以下の長いテキストを要約し、最も重要なポイントのみを含む簡潔な応答を生成してください。
        
        1. 最も重要な情報のみを抽出する
        2. 要約は元のテキストの10%以下の長さにする
        3. 箇条書きを使って読みやすくする
        4. コードブロックの例は短く簡潔にする、または省略する
        5. 技術的な正確さを保つ
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"以下のテキストを要約してください:\n\n{long_response}"
            ),
        ]

        response = await self.model_handler.llm.ainvoke(messages)
        return response.content

    def _format_code_blocks(self, text: str) -> str:
        """コードブロックの整形を行う
        Slackの表示に適したフォーマットに変換
        """
        # コードブロックの検出と整形のロジック
        # ここでは単純な実装例
        import re

        # Markdownのコードブロックを検出し、Slack用に整形
        pattern = r"```([a-zA-Z]*)\n([\s\S]*?)\n```"

        def replacement(match):
            lang = match.group(1) or ""
            code = match.group(2)
            return f"```{lang}\n{code}\n```"

        formatted_text = re.sub(pattern, replacement, text)
        return formatted_text

    def _format_mentions(self, text: str, mentions: Dict[str, str]) -> str:
        """メンションの整形を行う
        ユーザー名を適切なSlackメンションフォーマットに変換

        Args:
            text: 整形するテキスト
            mentions: ユーザー名とSlackユーザーIDのマッピング
        """
        # メンションパターンの検出と整形
        for username, user_id in mentions.items():
            # @username 形式をSlackメンション形式に変換
            text = text.replace(f"@{username}", f"<@{user_id}>")

        return text
