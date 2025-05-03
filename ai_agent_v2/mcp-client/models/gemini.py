"""
Google Gemini モデル処理モジュール

Geminiモデルとの連携と処理を担当します
"""

import google.generativeai as genai

from ..config import GEMINI_API_KEY, GEMINI_MODEL_NAME


class GeminiModelHandler:
    """
    Googleのgeminiモデルを処理するクラス
    """

    def __init__(self):
        """
        GeminiModelHandlerを初期化
        """
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        else:
            print("Warning: GEMINI_API_KEY not found in environment variables")

        self.gemini = genai.GenerativeModel(GEMINI_MODEL_NAME)

    async def process_query(self, query: str, mcp_tools, default_channel_id=None):
        """
        Google Gemini LLMを使用してクエリを処理

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト
            default_channel_id: デフォルトのSlackチャンネルID

        Returns:
            str: Geminiの応答
        """
        try:
            # Simple approach without trying to use tools
            gemini_prompt = f"""あなたはSlackに接続された日本語で対応するアシスタントです。
Slackの統合でできることをユーザーに説明することができます。
以下のSlackツールが利用可能です: {", ".join([tool.name for tool in mcp_tools])}

ユーザーの質問: {query}

ユーザーの質問に直接答えてください。簡易モードで実行されていることを日本語で説明してください。
日本語で丁寧に回答してください。
"""

            response = self.gemini.generate_content(
                contents=gemini_prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": 800},
            )

            return response.text
        except Exception as e:
            print(f"Error with Gemini API: {str(e)}")
            return f"申し訳ありません。リクエスト処理中にエラーが発生しました: {str(e)}"
