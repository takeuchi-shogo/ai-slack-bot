import logging  # logging をインポート
from typing import Any, Dict

from models.open_ai import OpenAIModelHandler

# from models.gemini import GeminiModelHandler # 将来のモデル追加用

# httpx や openai のエラークラスをインポートする必要があるかもしれません
# 例: from openai import APIError, APITimeoutError
# 例: import httpx
# (お使いのOpenAIライブラリがどのような例外を送出するかに依存します)
# from openai import APITimeoutError, APIConnectionError, RateLimitError, APIStatusError


logger = logging.getLogger(__name__)  # logger を設定

# エラーメッセージの日本語訳辞書
ERROR_MESSAGE_JA = {
    "timeout": "AI ({model_name}) への接続がタイムアウトしました。しばらくしてからもう一度お試しください。",
    "api_error": "AI ({model_name}) との通信中に一般的なエラーが発生しました。しばらくしてからもう一度お試しください。",  # 汎用的なAPIエラー
    "api_connection_error": "AI ({model_name}) との接続に失敗しました。ネットワーク状態などを確認してください。",
    "api_status_error": "AI ({model_name}) が内部エラーまたは不正なリクエストとして応答しました。しばらくしてからもう一度お試しください。",
    "quota_exceeded": "AI ({model_name}) の利用上限に達しました。管理者にお問い合わせください。",
    "empty_response": "AI ({model_name}) からの応答がありませんでした。もう一度お試しいただくか、管理者にお問い合わせください。",
    "unknown_model_error": "AI ({model_name}) の処理中に予期せぬモデル固有のエラーが発生しました。",
    "unknown_proxy_error": "システム処理中に予期せぬエラーが発生しました。管理者にお問い合わせください。",
}


class UserProxyAgent:
    """
    ユーザーからのクエリを分析し、必要なエージェントとアクションを決定する
    """

    def __init__(self, model_type: str = "openai"):
        if model_type == "openai":
            self.model_handler = OpenAIModelHandler()
        # elif model_type == "gemini":
        #     self.model_handler = GeminiModelHandler() # 将来の拡張用
        else:
            # サポートしていないモデルタイプの場合はエラーを発生させるか、デフォルトを持つ
            logger.warning(
                f"Unsupported model_type: {model_type}, defaulting to OpenAI."
            )
            self.model_handler = (
                OpenAIModelHandler()
            )  # フォールバックとしてOpenAIを使用する例

    async def execute(self, query: str) -> Dict[str, Any]:
        """ユーザークエリを分析し、必要なエージェントとアクションを決定する

        Args:
            query (str): ユーザーからのクエリ文字列

        Returns:
            Dict[str, Any]: 分析結果（content, is_need_data, error_occurred, error_type など）
        """
        prompt_messages = [
            {
                "role": "system",
                "content": "あなたはユーザークエリを分析し、適切な対応方法を提案するアシスタントです。",
            },
            {
                "role": "user",
                "content": f"以下のユーザークエリを分析し、必要な対応を判断してください：\n\nユーザークエリ：\n{query}\n\n分析結果：\n",
            },
        ]

        try:
            llm_response = await self.model_handler.invoke_llm(prompt_messages)
            model_name = llm_response.get("model_name", "不明なAI")

            if not llm_response.get("success"):
                error_type = llm_response.get("error_type", "unknown_model_error")
                original_error_detail = str(llm_response.get("original_error", ""))
                logger.error(
                    f"UserProxyAgent: Error from {model_name} - Type: {error_type}, Details: {original_error_detail}"
                )

                # ERROR_MESSAGE_JA からメッセージを取得、見つからなければ unknown_model_error を使用
                error_message_template = ERROR_MESSAGE_JA.get(
                    error_type, ERROR_MESSAGE_JA["unknown_model_error"]
                )
                error_message = error_message_template.format(model_name=model_name)

                return {
                    "content": error_message,
                    "is_need_data": False,
                    "error_occurred": True,
                    "error_type": error_type,
                    "model_name": model_name,
                }

            response_content = llm_response.get("content")

            if not response_content:
                logger.warning(f"UserProxyAgent: Empty response from {model_name}.")
                return {
                    "content": ERROR_MESSAGE_JA["empty_response"].format(
                        model_name=model_name
                    ),
                    "is_need_data": False,
                    "error_occurred": True,
                    "error_type": "empty_response",
                    "model_name": model_name,
                }

            return {
                "content": response_content,
                "is_need_data": "データベース" in response_content
                or "ログ" in response_content,
                "error_occurred": False,
                "model_name": model_name,
            }

        except Exception as e:
            # このExceptionは invoke_llm 呼び出し自体や、その前後処理でのUserProxyAgent内の予期せぬエラー
            current_model_name = getattr(self.model_handler, "MODEL_NAME", "N/A")
            logger.error(
                f"UserProxyAgent: Unexpected internal error while processing with {current_model_name} - {type(e).__name__}: {str(e)}"
            )
            return {
                "content": ERROR_MESSAGE_JA[
                    "unknown_proxy_error"
                ],  # model_name はここでは無関係か、システム固定
                "is_need_data": False,
                "error_occurred": True,
                "error_type": "unknown_proxy_error",  # UserProxyAgentレベルのエラーを示す
                "model_name": current_model_name,
            }
