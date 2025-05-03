"""
ユーティリティ関数モジュール

様々なヘルパー関数を提供します
"""

import json


def extract_tool_content(content):
    """
    ツール応答からテキストコンテンツを抽出

    Args:
        content: ツール呼び出しの結果

    Returns:
        str: 抽出されたテキストコンテンツ
    """
    if hasattr(content, "__iter__") and not isinstance(content, str):
        # It's an iterable of TextContent objects
        result_texts = []
        for item in content:
            if hasattr(item, "text"):
                result_texts.append(item.text)
        return "".join(result_texts)
    else:
        # It's a single value
        return str(content)


def analyze_code_issues(code_content, search_term):
    """
    コードの問題点を分析

    Args:
        code_content: 分析するコードコンテンツ
        search_term: 検索に使用した用語

    Returns:
        str: 検出された問題点の説明
    """
    issues = []

    # 明らかなコードの問題を検出
    if "TODO" in code_content:
        issues.append("未完了の TODO コメントが含まれています")

    if "FIXME" in code_content:
        issues.append("修正が必要な FIXME コメントが含まれています")

    if "BUG" in code_content or "bug" in code_content.lower():
        issues.append("バグに関する言及があります")

    # セキュリティ関連の問題
    if any(
        term in code_content.lower()
        for term in ["password", "secret", "key", "token", "パスワード", "秘密"]
    ):
        if any(term in code_content.lower() for term in ["hardcoded", "ハードコード"]):
            issues.append("ハードコードされた機密情報が含まれている可能性があります")

    # エラーハンドリング
    if (
        "try" in code_content.lower()
        and "except" not in code_content.lower()
        and "catch" not in code_content.lower()
    ):
        issues.append("エラーハンドリングが不完全な可能性があります")

    # 検索語に基づく分析
    if search_term.lower() in code_content.lower():
        lines_with_term = [
            line.strip()
            for line in code_content.split("\n")
            if search_term.lower() in line.lower()
        ]
        if lines_with_term:
            term_context = "\n".join(lines_with_term[:3])  # 最初の3行まで
            issues.append(f"検索語「{search_term}」を含む箇所:\n{term_context}")

    # パフォーマンスの問題
    if "for" in code_content.lower() and "for" in code_content.lower().split("for")[1]:
        issues.append(
            "ネストされたループがあり、パフォーマンスの問題がある可能性があります"
        )

    # 結果を返す
    if issues:
        return "- " + "\n- ".join(issues)
    else:
        return "明らかな問題は検出されませんでした"


def process_tool_arguments(tool_name, tool_args, default_channel_id=None):
    """
    ツール引数を処理し、実行のために準備

    Args:
        tool_name: 呼び出すツールの名前
        tool_args: ツールに渡す引数（文字列または辞書）
        default_channel_id: デフォルトのSlackチャンネルID

    Returns:
        dict: 処理された引数辞書
    """
    if isinstance(tool_args, str) and tool_args.strip() == "{}":
        # Empty JSON object as string - convert to empty dict
        tool_args_dict = {}
    elif isinstance(tool_args, str) and tool_args.strip().startswith("{"):
        # Try to parse as JSON string
        try:
            tool_args_dict = json.loads(tool_args)
        except json.JSONDecodeError:
            tool_args_dict = {"text": tool_args}
    else:
        # Already a dict or other input
        tool_args_dict = (
            tool_args if isinstance(tool_args, dict) else {"text": tool_args}
        )

    # Add default channel_id if available and needed for Slack tools
    if default_channel_id and "channel_id" not in tool_args_dict:
        if tool_name.startswith("slack_") and (
            "channel" in tool_name
            or tool_name == "slack_post_message"
            or tool_name == "slack_reply_to_thread"
        ):
            tool_args_dict["channel_id"] = default_channel_id

    # For slack_post_message, make sure we have text
    if tool_name == "slack_post_message" and "text" not in tool_args_dict:
        # Try to extract text from context
        if isinstance(tool_args, str) and not tool_args.startswith("{"):
            tool_args_dict["text"] = tool_args.strip()

    return tool_args_dict
