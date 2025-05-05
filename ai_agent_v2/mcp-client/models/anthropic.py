"""
Anthropic (Claude) モデル処理モジュール

Claudeモデルとの連携と処理を担当します
LangChainを使用して実装
"""

import json
from typing import List

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_NAME,
    MAX_TOKENS,
    MODEL_TEMPERATURE,
    SYSTEM_PROMPT,
)
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool


class AnthropicModelHandler:
    """
    Anthropicモデル（Claude）を処理するクラス
    LangChainを使用して実装
    """

    def __init__(self):
        """
        AnthropicModelHandlerを初期化
        LangChain ChatAnthropicモデルを設定
        """
        if not ANTHROPIC_API_KEY:
            print("Warning: ANTHROPIC_API_KEY not found in environment variables")

        # LangChain ChatAnthropicモデルの初期化
        self.llm = ChatAnthropic(
            model=ANTHROPIC_MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )

        # システムプロンプトの設定
        self.system_prompt = SYSTEM_PROMPT

    def _convert_tools_for_langchain(self, mcp_tools) -> List[Tool]:
        """
        MCPツールをLangChainのTool形式に変換

        Args:
            mcp_tools: MCPツールのリスト

        Returns:
            List[Tool]: LangChainのツールリスト
        """
        tools = []

        for tool in mcp_tools:
            # 入力スキーマの処理
            try:
                input_schema = (
                    json.loads(tool.inputSchema)
                    if isinstance(tool.inputSchema, str)
                    else tool.inputSchema
                )
            except (TypeError, json.JSONDecodeError):
                input_schema = {"type": "object", "properties": {}}

            # ツールの関数を定義（後でtool_executorに渡す）
            async def tool_func(tool_name=tool.name, **kwargs):
                # この関数は実行時に適切なtool_executorを使ってオーバーライドされる
                pass

            # LangChainのTool形式に変換
            langchain_tool = Tool(
                name=tool.name, description=tool.description, func=tool_func
            )

            tools.append(langchain_tool)

        return tools

    async def process_query_simple(self, query: str):
        """
        簡易モードでLangChain経由でAnthropic Claude LLMを使用してクエリを処理 (ツールなし)

        Args:
            query: ユーザークエリ

        Returns:
            str: Claudeの応答
        """
        # プロンプトテンプレートの作成
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content="""あなたはSlackに接続された日本語で対応するアシスタントです。
簡易モードで実行されているため、外部サービスへの接続はできません。
ユーザーの質問に直接回答してください。
日本語で丁寧に回答してください。"""
                ),
                HumanMessage(content="{query}"),
            ]
        )

        # LangChainの実行チェーン
        chain = prompt | self.llm | StrOutputParser()

        try:
            # チェーンを実行して結果を取得
            result = await chain.ainvoke({"query": query})
            return result
        except Exception as e:
            print(f"Error calling Claude API via LangChain: {str(e)}")
            return f"Error with Claude API: {str(e)}"

    async def process_query(self, query: str, mcp_tools, tool_executor):
        """
        LangChain経由でAnthropic Claude LLMを使用してクエリを処理

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト
            tool_executor: ツール実行のためのコールバック関数

        Returns:
            str: Claudeの応答
        """
        # MCPツールをLangChainツールに変換
        langchain_tools = self._convert_tools_for_langchain(mcp_tools)

        # ダイナミックツール実行のためのラッパー関数を作成
        for tool in langchain_tools:
            # クロージャでツール名をキャプチャし、ツール実行関数をオーバーライド
            async def _wrapped_executor(tool_name=tool.name, **kwargs):
                return await tool_executor(tool_name, kwargs)

            # 各ツールの関数を割り当て（クロージャ）
            tool.func = _wrapped_executor

        # LangChain AgentのためのLLMにツールを設定
        llm_with_tools = self.llm.bind_tools(langchain_tools)

        # プロンプトテンプレートの作成
        prompt = ChatPromptTemplate.from_messages(
            [SystemMessage(content=self.system_prompt), HumanMessage(content="{query}")]
        )

        # LangChainの実行チェーン
        chain = prompt | llm_with_tools | StrOutputParser()

        try:
            # 処理の実行
            result = await chain.ainvoke({"query": query})
            return result
        except Exception as e:
            print(f"Error in LangChain execution: {str(e)}")
            return f"エラーが発生しました: {str(e)}"

    async def process_structured_query(self, query: str, mcp_tools, tool_executor):
        """
        構造化された結果を返すLangChainベースのクエリ処理
        上級者向け機能として実装（JSONなどの構造化データが必要な場合に使用）

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト
            tool_executor: ツール実行のためのコールバック関数

        Returns:
            Dict: Claudeの構造化された応答
        """
        from langchain_core.output_parsers import JsonOutputParser

        # MCPツールをLangChainツールに変換
        langchain_tools = self._convert_tools_for_langchain(mcp_tools)

        # ツール実行関数の設定
        for tool in langchain_tools:

            async def _wrapped_executor(tool_name=tool.name, **kwargs):
                return await tool_executor(tool_name, kwargs)

            tool.func = _wrapped_executor

        # JSON出力パーサーの設定
        json_parser = JsonOutputParser()

        # LLMにツールを設定
        llm_with_tools = self.llm.bind_tools(langchain_tools)

        # JSONレスポンスを要求するプロンプト
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=f"{self.system_prompt}\n応答はJSON形式で構造化してください。"
                ),
                HumanMessage(content="{query}"),
            ]
        )

        # JSON出力を生成するチェーン
        chain = prompt | llm_with_tools | json_parser

        try:
            # チェーンを実行して構造化された結果を取得
            result = await chain.ainvoke({"query": query})
            return result
        except Exception as e:
            print(f"Error in structured LangChain execution: {str(e)}")
            return {
                "error": str(e),
                "message": "JSONレスポンスの生成中にエラーが発生しました",
            }
