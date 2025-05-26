import logging

from config.model import (
    MAX_TOKENS,
    MODEL_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
)
from langchain_openai import ChatOpenAI

# OpenAI のエラークラスをインポート (バージョンによって異なる可能性あり、要確認)
from openai import (  # v1.x系を想定
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

logger = logging.getLogger(__name__)  # logger を設定


class OpenAIModelHandler:
    MODEL_NAME = "OpenAI"  # モデル名をクラス変数として定義

    def __init__(self):
        self._llm = None
        self._initialized = False

    @property
    def llm(self):
        """遅延初期化でChatOpenAIインスタンスを取得"""
        if not self._initialized:
            self._llm = ChatOpenAI(
                model=OPENAI_MODEL_NAME,
                temperature=MODEL_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                openai_api_key=OPENAI_API_KEY,
                # request_timeout=60, # 必要に応じてタイムアウトを設定 (例: 60秒)
            )
            self._initialized = True
        return self._llm

    async def aclose(self):
        """HTTPクライアントを適切に閉じる"""
        if (
            self._llm
            and hasattr(self._llm, "client")
            and hasattr(self._llm.client, "close")
        ):
            try:
                if hasattr(self._llm.client, "aclose"):
                    await self._llm.client.aclose()
                else:
                    self._llm.client.close()
                logger.info(f"{self.MODEL_NAME} HTTPクライアントを正常に閉じました")
            except Exception as e:
                logger.warning(
                    f"{self.MODEL_NAME} HTTPクライアントのクローズ中にエラー: {str(e)}"
                )
        self._llm = None
        self._initialized = False

    def __del__(self):
        """デストラクタでのクリーンアップ（フォールバック）"""
        if self._llm:
            try:
                # 同期的なクリーンアップのみ実行
                if hasattr(self._llm, "client") and hasattr(self._llm.client, "close"):
                    self._llm.client.close()
            except Exception:
                pass  # デストラクタでは例外を無視

    async def invoke_llm(self, messages: list) -> dict:
        """
        LangChainのChatOpenAIを使用してLLMを呼び出し、結果とエラー情報を標準化して返す。

        Args:
            messages: LLMに渡すメッセージのリスト。

        Returns:
            dict: 成功時は {"success": True, "content": "...", "model_name": "OpenAI"}
                  失敗時は {"success": False, "error_type": "...", "original_error": e, "model_name": "OpenAI"}
        """
        try:
            response = await self.llm.ainvoke(messages)
            return {
                "success": True,
                "content": response.content,
                "model_name": self.MODEL_NAME,
            }
        except APITimeoutError as e:
            logger.error(f"{self.MODEL_NAME} API Timeout: {str(e)}")
            return {
                "success": False,
                "error_type": "timeout",
                "original_error": e,
                "model_name": self.MODEL_NAME,
            }
        except RateLimitError as e:
            logger.error(f"{self.MODEL_NAME} API Rate Limit Exceeded: {str(e)}")
            return {
                "success": False,
                "error_type": "quota_exceeded",
                "original_error": e,
                "model_name": self.MODEL_NAME,
            }
        except APIConnectionError as e:  # ネットワーク接続関連の問題
            logger.error(f"{self.MODEL_NAME} API Connection Error: {str(e)}")
            return {
                "success": False,
                "error_type": "api_connection_error",
                "original_error": e,
                "model_name": self.MODEL_NAME,
            }
        except APIStatusError as e:  # APIがエラーステータスを返した場合 (例: 4xx, 5xx)
            logger.error(
                f"{self.MODEL_NAME} API Status Error - Status: {e.status_code}, Response: {e.response}"
            )
            # e.status_code によって error_type をより詳細に分岐することも可能
            # (例: 401なら "authentication_error", 429なら "quota_exceeded" (RateLimitErrorと重複する可能性あり))
            return {
                "success": False,
                "error_type": "api_status_error",
                "original_error": e,
                "model_name": self.MODEL_NAME,
            }
        except Exception as e:
            logger.error(
                f"{self.MODEL_NAME} LLM Call - Unexpected Error - {type(e).__name__}: {str(e)}"
            )
            # ここでは OpenAI SDK が送出する上記以外の予期せぬエラー、または langchain_openai 内部のエラーを想定
            return {
                "success": False,
                "error_type": "unknown_model_error",
                "original_error": e,
                "model_name": self.MODEL_NAME,
            }
