# AI Agent V2 - LangChain MCP ワークフローグラフの概要

このディレクトリは、LangChain MCP（Model Context Protocol）を用いたワークフロー管理のための実装を含みます。

## ワークフローグラフの構成

以下は、`core/workflow_manager.py` で定義されている更新後のワークフローグラフの構成です。

```
[START]
   |
   v
[analyze_query] ────┬──> [search_database] ────┬──> [review_github_code] ───┐
                    |                          |                            |
                    |                          v                            |
                    └───────────────────> [route_to_agent] <───────────────┘
                                              |
                                              v
                                     [create_notion_task]
                                              |
                                              v
                                     [send_slack_response]
                                              |
                                              v
                                            [END]
```

### ノードの説明

- **analyze_query**
  - ユーザーからのクエリを解析し、処理方針を決定します。
  - DB検索やGithubコードレビューが必要かどうかも判断します。
- **search_database**
  - 必要に応じてデータベースやログの検索を実行します。
- **review_github_code**
  - 必要に応じてGithubからコードを取得し、問題箇所のレビューを行います。
- **route_to_agent**
  - クエリ内容と検索/レビュー結果に応じて適切なエージェントにルーティングします。
- **create_notion_task**
  - 問題が特定された場合にはNotionにタスクを作成します。
- **send_slack_response**
  - 最終的な応答をSlackに送信します。

## グラフの更新実装例

```python
# ワークフローグラフの定義
workflow = StateGraph(state_schema={"query": str})

# ノードの追加
workflow.add_node("analyze_query", analyze_query)
workflow.add_node("search_database", search_database)
workflow.add_node("review_github_code", review_github_code)
workflow.add_node("route_to_agent", route_to_agent)
workflow.add_node("create_notion_task", create_notion_task)
workflow.add_node("send_slack_response", send_slack_response)

# 条件分岐エッジの追加
workflow.add_conditional_edges(
    "analyze_query",
    should_search_database,
    {
        "search_database": "search_database",
        "review_github_code": "review_github_code",
        "route_to_agent": "route_to_agent"
    }
)

workflow.add_conditional_edges(
    "search_database",
    after_db_search,
    {
        "review_github_code": "review_github_code",
        "route_to_agent": "route_to_agent"
    }
)

workflow.add_edge("review_github_code", "route_to_agent")

# 固定エッジの追加
workflow.add_edge("route_to_agent", "create_notion_task")
workflow.add_edge("create_notion_task", "send_slack_response")
workflow.add_edge("send_slack_response", END)

# スタートノードの設定
workflow.set_entry_point("analyze_query")

return workflow.compile()
```

## 図解

```mermaid
graph TD;
    START --> analyze_query
    analyze_query -->|DB検索が必要| search_database
    analyze_query -->|GitHubレビューが必要| review_github_code
    analyze_query -->|どちらも不要| route_to_agent
    search_database -->|GitHubレビューが必要| review_github_code
    search_database -->|GitHubレビュー不要| route_to_agent
    review_github_code --> route_to_agent
    route_to_agent --> create_notion_task
    create_notion_task --> send_slack_response
    send_slack_response --> END
```

---

この更新されたグラフは、ユーザークエリを分析した後、必要に応じてデータベース検索やGitHubコードレビューを行い、
その結果を適切なエージェントに渡して処理する流れを表しています。問題が見つかった場合はNotionタスクが作成され、
最終的にSlackに応答が送信されます。
