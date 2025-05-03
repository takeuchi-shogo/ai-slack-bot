# MCP Client

## 概要

MCP Client は、Model Context Protocol (MCP) サーバーと通信するための Python クライアントです。SlackやGitHubなどの外部サービスとの連携を可能にし、大規模言語モデル（LLM）を使用してこれらのサービスとインタラクションできます。

## アーキテクチャ

### 基本アーキテクチャ

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│    ユーザー    │────→│  MCP クライアント │────→│  MCP サーバー  │
│              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                    │
                            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐
                     │              │     │              │
                     │   LLM (API)   │     │ 外部サービス   │
                     │              │     │ (Slack/GitHub)│
                     └──────────────┘     └──────────────┘
```

### マルチサーバー連携アーキテクチャ

```
┌──────────────┐     ┌──────────────┐
│              │     │              │
│    ユーザー    │────→│  MCP クライアント │
│              │     │              │
└──────────────┘     └──────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
     ┌──────────────┐             ┌──────────────┐
     │              │             │              │
     │ GitHub サーバー │             │ Slack サーバー │
     │              │             │              │
     └──────────────┘             └──────────────┘
              │                           │
              │                           │
              ▼                           ▼
     ┌──────────────┐             ┌──────────────┐
     │              │             │              │
     │ GitHub API   │             │ Slack API    │
     │              │             │              │
     └──────────────┘             └──────────────┘
```

## 処理フロー

### 通常の処理フロー

1. ユーザーがクエリを入力
2. MCPクライアントがクエリを処理
3. 選択されたLLM（GeminiまたはClaude）にクエリを送信
4. LLMがクエリを分析し、必要に応じてツール呼び出しを生成
5. MCPクライアントがツール呼び出しを実行
6. 結果をLLMに返送し、最終的な応答を生成
7. ユーザーに結果を表示

### クロスサーバー処理フロー（GitHub → Slack）

1. ユーザーがGitHubとSlackに関連するクエリを入力
2. クエリからクロスサーバー操作と判断
3. GitHubサーバーに接続
4. GitHubから情報を取得
5. GitHubサーバーとの接続を閉じる
6. Slackサーバーに接続
7. 取得したGitHub情報をSlackに投稿
8. 処理結果をユーザーに返送

## 機能と実装

### MCPClient クラス

クライアントの中核となるクラスで、MCPサーバーとの接続や通信を管理します。

#### 主要メソッド

| メソッド名 | 説明 |
|------------|------|
| `__init__` | クライアントの初期化。モデルプロバイダー（geminiまたはanthropic）を設定 |
| `connect_to_server` | 指定されたMCPサーバー（SlackやGitHubなど）に接続 |
| `process_query` | ユーザークエリを処理。適切な処理方法を決定 |
| `_process_cross_server_query` | 複数サーバー間の連携処理を実行 |
| `_process_with_anthropic` | Claude（Anthropic）を使用してクエリを処理 |
| `_process_with_gemini` | Gemini（Google）を使用してクエリを処理 |
| `_extract_github_info` | GitHubからの情報取得を処理 |
| `_post_to_slack` | Slackへの投稿を処理 |
| `_process_claude_response` | Claude応答の処理とツール呼び出しの管理 |
| `_process_tool_arguments` | ツール引数の処理と準備 |
| `_execute_tool_call` | ツール呼び出しの実行 |
| `_extract_tool_content` | ツール応答からのコンテンツ抽出 |
| `chat_loop` | 対話型のチャットループを実行 |
| `cleanup` | リソースのクリーンアップ |

## 設定ファイル

### スキーマファイル

`schema` ディレクトリには各サーバーの設定を含むJSONファイルがあります：

- `slack.json`: Slack MCPサーバーの設定
- `github.json`: GitHub MCPサーバーの設定

## 使用方法

```bash
# Geminiモード（デフォルト、シンプル）でSlackサーバーに接続
uv run client.py --server slack

# Anthropicモード（フル機能）でSlackサーバーに接続
uv run client.py --server slack --model anthropic

# GitHubサーバーに接続
uv run client.py --server github
```

## 依存関係

- `anthropic`: Claude APIとの通信
- `google-generativeai`: Gemini APIとの通信
- `mcp`: Model Context Protocol実装
- `python-dotenv`: 環境変数の読み込み

## 拡張性

このクライアントは、新しいMCPサーバーの追加が容易な設計になっています。新しいサービスを追加するには：

1. 対応するスキーマファイルを `schema` ディレクトリに追加
2. 必要に応じてクロスサーバー処理ロジックを拡張

## 参考URL

- [Model Context Protocol](https://modelcontextprotocol.io/quickstart/client)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- [Google Gemini API](https://ai.google.dev/docs)