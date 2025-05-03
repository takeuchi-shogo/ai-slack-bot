"""
Anthropic (Claude) モデル処理モジュール

Claudeモデルとの連携と処理を担当します
"""

import json

from anthropic import Anthropic

from ..config import ANTHROPIC_MODEL_NAME


class AnthropicModelHandler:
    """
    Anthropicモデル（Claude）を処理するクラス
    """

    def __init__(self):
        """
        AnthropicModelHandlerを初期化
        """
        self.anthropic = Anthropic()

    def _format_tools_for_claude(self, mcp_tools):
        """
        MCPツールをClaude用のフォーマットに変換

        Args:
            mcp_tools: MCPツールのリスト

        Returns:
            list: Claudeのツール形式に変換されたリスト
        """
        tools_json = []
        for tool in mcp_tools:
            # Handle inputSchema - may already be parsed JSON object or a string
            try:
                input_schema = (
                    json.loads(tool.inputSchema)
                    if isinstance(tool.inputSchema, str)
                    else tool.inputSchema
                )
            except (TypeError, json.JSONDecodeError):
                input_schema = {"type": "object", "properties": {}}

            tool_json = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": input_schema,
            }
            tools_json.append(tool_json)

        return tools_json

    async def process_query(self, query: str, mcp_tools, tool_executor):
        """
        Anthropic Claude LLMを使用してクエリを処理

        Args:
            query: ユーザークエリ
            mcp_tools: 利用可能なMCPツールのリスト
            tool_executor: ツール実行のためのコールバック関数

        Returns:
            str: Claudeの応答
        """
        # Format tools for Claude
        tools_json = self._format_tools_for_claude(mcp_tools)

        # Initial message to Claude
        messages = [{"role": "user", "content": query}]

        # Claude API call
        try:
            response = self.anthropic.messages.create(
                model=ANTHROPIC_MODEL_NAME,
                max_tokens=1000,
                messages=messages,
                tools=tools_json,
            )

            # Process Claude response
            return await self._process_claude_response(
                response, messages, tools_json, tool_executor
            )
        except Exception as e:
            print(f"Error calling Claude API: {str(e)}")
            return f"Error with Claude API: {str(e)}"

    async def _process_claude_response(
        self, response, messages, tools_json, tool_executor
    ):
        """
        Claude APIからの応答を処理

        Args:
            response: Claude APIのレスポンスオブジェクト
            messages: 会話履歴
            tools_json: 利用可能なツールの定義（JSON形式）
            tool_executor: ツール実行関数

        Returns:
            str: 最終的なテキスト応答
        """
        final_text = []
        conversation_history = messages.copy()

        while True:
            # Extract text content
            assistant_message = {"role": "assistant", "content": []}
            has_tool_use = False

            for content in response.content:
                if content.type == "text":
                    final_text.append(content.text)
                    assistant_message["content"].append(
                        {"type": "text", "text": content.text}
                    )
                elif content.type == "tool_use":
                    has_tool_use = True
                    # Handle the Claude API format for tool calls
                    tool_name = content.name
                    tool_args = content.input
                    tool_id = content.id

                    # Format tool_use correctly
                    assistant_message["content"].append(
                        {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool_name,
                            "input": tool_args,
                        }
                    )

                    # Execute tool call
                    result_content = await tool_executor(tool_name, tool_args)

                    # Add tool result to conversation
                    conversation_history.append(assistant_message)
                    conversation_history.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": result_content
                                    if isinstance(result_content, str)
                                    else json.dumps(result_content),
                                }
                            ],
                        }
                    )

                    # Get next response from Claude
                    response = self.anthropic.messages.create(
                        model=ANTHROPIC_MODEL_NAME,
                        max_tokens=1000,
                        messages=conversation_history,
                        tools=tools_json,
                    )

                    # Continue processing the new response
                    break
            else:
                # No tool calls in this response, we're done
                conversation_history.append(assistant_message)
                # If we never had any tool calls, just return the text
                if not has_tool_use:
                    print("No tool calls were made, returning direct response")
                break

        return "\n".join(final_text)
