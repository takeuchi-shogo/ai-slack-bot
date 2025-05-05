# MCP Client

## 概要

MCP Client は、Model Context Protocol (MCP) サーバーと通信するための Python クライアントです。SlackやGitHub、Notionなどの外部サービスとの連携を可能にし、大規模言語モデル（LLM）を使用してこれらのサービスとインタラクションできます。コードの問題を検出し、Notionにタスクを作成し、Slackで結果を共有するクロスサーバーワークフローをサポートします。

LangChainフレームワークを活用しており、モデルとツールの連携を効率的に実現します。簡易モードと完全モードの2つの動作モードに対応し、外部サービスへのアクセスなしでモデルを直接利用することも、フルAPIアクセスを行うこともできます。

## コード構成

```
mcp-client/
├── client.py (メインエントリーポイント)
├── config.py (設定管理)
├── core/
│   ├── __init__.py
│   ├── base.py (ベースクラスと共通機能)
│   ├── session.py (サーバー接続とセッション管理)
│   └── utils.py (ユーティリティ関数)
├── database/
│   ├── __init__.py
│   ├── agent.py (データベースクエリエージェント)
│   ├── connection.py (データベース接続管理)
│   └── query.py (自然言語→SQL変換)
├── models/
│   ├── __init__.py
│   ├── anthropic.py (Anthropic/Claude関連)
│   └── gemini.py (Google Gemini関連)
├── services/
│   ├── __init__.py
│   ├── github.py (GitHub関連機能)
│   ├── notion.py (Notion関連機能)
│   └── slack.py (Slack関連機能)
├── tools/
│   ├── __init__.py
│   └── handlers.py (ツール呼び出し処理)
└── schema/
    ├── github.json
    ├── notion.json
    └── slack.json
```

## アーキテクチャ

### 基本アーキテクチャ

#### 完全モード (Full Mode)

```mermaid
graph TD
    A[ユーザー] --> B[MCP クライアント]
    B --> C[MCP サーバー]
    B --> D[LLM API]
    C --> E[外部サービス\nSlack/GitHub/Notion]
    
    classDef user fill:#d0e0ff,stroke:#333,stroke-width:1px;
    classDef client fill:#ffe6cc,stroke:#333,stroke-width:1px;
    classDef server fill:#d5e8d4,stroke:#333,stroke-width:1px;
    classDef api fill:#fff2cc,stroke:#333,stroke-width:1px;
    classDef service fill:#f8cecc,stroke:#333,stroke-width:1px;
    
    class A user;
    class B client;
    class C server;
    class D api;
    class E service;
```

#### 簡易モード (Simple Mode)

```mermaid
graph TD
    A[ユーザー] --> B[MCP クライアント]
    B --> D[LLM API\nClaude/Gemini]
    
    classDef user fill:#d0e0ff,stroke:#333,stroke-width:1px;
    classDef client fill:#ffe6cc,stroke:#333,stroke-width:1px;
    classDef api fill:#fff2cc,stroke:#333,stroke-width:1px;
    
    class A user;
    class B client;
    class D api;
```

### マルチサーバー連携アーキテクチャ

```mermaid
graph TD
    A[ユーザー] --> B[MCP クライアント]
    B --> C[GitHub サーバー]
    B --> D[Notion サーバー]
    B --> E[Slack サーバー]
    C --> F[GitHub API]
    D --> G[Notion API]
    E --> H[Slack API]
    
    classDef user fill:#d0e0ff,stroke:#333,stroke-width:1px;
    classDef client fill:#ffe6cc,stroke:#333,stroke-width:1px;
    classDef github fill:#d5e8d4,stroke:#333,stroke-width:1px;
    classDef notion fill:#fff2cc,stroke:#333,stroke-width:1px;
    classDef slack fill:#f8cecc,stroke:#333,stroke-width:1px;
    classDef api fill:#e1d5e7,stroke:#333,stroke-width:1px;
    
    class A user;
    class B client;
    class C github;
    class D notion;
    class E slack;
    class F,G,H api;
```

### データベース連携アーキテクチャ

```mermaid
graph TD
    A[ユーザー] --> B[MCP クライアント]
    B --> C[LLM (Claude/Gemini)]
    B --> D[データベースエージェント]
    D --> E[自然言語→SQL変換]
    D --> F[データベース接続]
    F --> G[データベース\nMySQL/PostgreSQL/SQLite]
    
    classDef user fill:#d0e0ff,stroke:#333,stroke-width:1px;
    classDef client fill:#ffe6cc,stroke:#333,stroke-width:1px;
    classDef llm fill:#fff2cc,stroke:#333,stroke-width:1px;
    classDef db fill:#d5e8d4,stroke:#333,stroke-width:1px;
    classDef service fill:#f8cecc,stroke:#333,stroke-width:1px;
    
    class A user;
    class B client;
    class C llm;
    class D,E,F db;
    class G service;
```

## 処理フロー

### 基本的な処理フロー

#### 完全モードの処理フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Client as MCPクライアント
    participant LLM as LLM (Claude/Gemini)
    participant MCP as MCPサーバー
    participant Service as 外部サービス
    
    User->>Client: クエリ入力
    Client->>LLM: クエリ送信
    LLM->>LLM: クエリ分析
    LLM->>Client: ツール呼び出し要求
    Client->>MCP: ツール呼び出し
    MCP->>Service: API呼び出し
    Service->>MCP: 結果返送
    MCP->>Client: ツール呼び出し結果
    Client->>LLM: 結果送信
    LLM->>LLM: 応答生成
    LLM->>Client: 最終応答
    Client->>User: 結果表示
```

#### 簡易モードの処理フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Client as MCPクライアント
    participant LLM as LLM (Claude/Gemini)
    
    User->>Client: クエリ入力
    Client->>LLM: クエリ送信（簡易モード）
    LLM->>LLM: クエリ処理
    LLM->>Client: 応答生成
    Client->>User: 結果表示
```

### クロスサーバー処理フロー（GitHub → Notion → Slack）

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Client as MCPクライアント
    participant GitHub as GitHubサーバー
    participant Notion as Notionサーバー
    participant Slack as Slackサーバー
    
    User->>Client: コード問題に関するクエリ
    Client->>GitHub: 接続
    Client->>GitHub: コード検索・分析要求
    GitHub->>Client: コード情報・問題分析結果
    Client->>GitHub: 切断
    
    alt 問題が検出された場合
        Client->>Notion: 接続
        Client->>Notion: タスク作成要求
        Notion->>Client: タスク作成結果
        Client->>Notion: 切断
    end
    
    Client->>Slack: 接続
    
    alt スレッド返信の場合
        Client->>Slack: スレッドにメンション付き返信
    else 新規メッセージの場合
        Client->>Slack: 結果要約を投稿
    end
    
    Slack->>Client: 投稿結果
    Client->>User: 処理結果報告
```

### データベースクエリ処理フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant Client as MCPクライアント
    participant Agent as データベースエージェント
    participant LLM as LLM (Claude/Gemini)
    participant NL2SQL as 自然言語→SQL変換
    participant DB as データベース
    
    User->>Client: 自然言語クエリ
    Client->>Agent: クエリ分析要求
    Agent->>LLM: クエリがDB関連か判断要求
    LLM->>Agent: 判断結果
    
    alt DBクエリと判断された場合
        Agent->>NL2SQL: SQL生成要求
        NL2SQL->>DB: スキーマ情報取得
        DB->>NL2SQL: スキーマ情報
        NL2SQL->>LLM: SQL生成
        LLM->>NL2SQL: 生成されたSQL
        NL2SQL->>DB: SQLクエリ実行
        DB->>NL2SQL: クエリ結果
        NL2SQL->>LLM: 結果の日本語説明要求
        LLM->>NL2SQL: 日本語説明
        NL2SQL->>Agent: クエリ結果と説明
        Agent->>Client: 処理結果
    else 非DBクエリの場合
        Agent->>Client: 非DBクエリとして報告
        Client->>LLM: 通常の処理へ
    end
    
    Client->>User: 応答表示
```

## 主要クラスとモジュール

### メインクラス

- **MCPClient**: メインのクライアントクラスで、簡易モードと完全モードの両方を処理します
  - 接続モード: `ConnectionMode.SIMPLE`（簡易モード）または`ConnectionMode.FULL`（完全モード）
  - モデルプロバイダー: `anthropic`（Claude）または`gemini`（Google Gemini）
  - 簡易モードでは直接モデルAPIを呼び出し、完全モードではサーバー接続と複雑な操作を処理します
  - LangChain統合: 会話履歴の追跡、プロンプト管理、ツール連携を実現

### コアモジュール (core/)

- **BaseMCPClient**: 基本的なセッション管理とクリーンアップ機能を提供
- **SessionManager**: MCPサーバーとの接続管理、LangChainツールの準備と管理
- **ServerConnector**: サーバーパラメータ生成
- **MCPToolWrapper**: MCPツールをLangChainのToolとしてラップする

### モデルモジュール (models/)

- **AnthropicModelHandler**: LangChain経由でClaude APIを利用した処理（簡易モード・完全モード対応）
  - `process_query_simple`: 簡易モードでの処理
  - `process_query`: 完全モードでの処理（ツール利用）
  - `process_structured_query`: JSON形式の構造化出力を生成
- **GeminiModelHandler**: LangChain経由でGemini APIを利用した処理（簡易モード・完全モード対応）
  - `process_query_simple`: 簡易モードでの処理
  - `process_query`: 完全モードでの処理（ツール利用）
  - `process_structured_query`: JSON形式の構造化出力を生成

### ツールモジュール (tools/)

- **ToolManager**: MCPツールの管理と呼び出し、LangChainツールの生成と管理
- **LangChainToolAdapter**: MCPツールをLangChainのToolとして利用するためのアダプターを提供

### サービスモジュール (services/)

- **GitHubService**: GitHub連携機能
- **NotionService**: Notion連携機能
- **SlackService**: Slack連携機能

### データベースモジュール (database/)

- **DatabaseConnection**: データベース接続を管理するクラス
  - `connect()`: データベースに接続
  - `execute_raw_query()`: SQLクエリを実行
  - `get_schema_info()`: データベーススキーマの説明を取得
  - LangChainのSQLDatabaseを内部的に使用
- **NaturalLanguageQueryProcessor**: 自然言語からSQLクエリを生成するクラス
  - `process_query()`: 自然言語クエリを処理しSQL実行結果を返す
  - LangChainのSQL生成チェーンを使用
- **DatabaseQueryAgent**: 自然言語でデータベースに問い合わせるエージェント
  - `is_database_query()`: クエリがデータベース関連かを判断
  - `process_query()`: 適切な処理を選択して実行

### 設定モジュール (config.py)

- 環境変数の管理
- モデル設定
- LangChain関連の設定（温度、トークン制限、システムプロンプト）
- サーバースキーマの読み込み
- データベース設定（タイプ、接続情報、スキーマ説明）

## 使用方法

### 動作モード

MCPクライアントには2つの動作モードがあります：

- **簡易モード (simple)**: 外部サービスに接続せず、LLMに直接クエリを送信します。API連携を必要としない簡単な質問や会話に適しています。
- **完全モード (full)**: MCPサーバーを介して外部サービス（Slack、GitHub、Notion）に接続し、APIツールを利用した高度な機能を提供します。

### 基本的なコマンド

```bash
# 簡易モード - Gemini (外部サービス連携なし)
uv run client.py --mode simple --model gemini

# 簡易モード - Claude (外部サービス連携なし)
uv run client.py --mode simple --model anthropic

# 完全モード - Gemini - Slackサーバーに接続
uv run client.py --mode full --server slack --model gemini

# 完全モード - Claude - Slackサーバーに接続
uv run client.py --mode full --server slack --model anthropic

# 完全モード - GitHubサーバーに接続
uv run client.py --mode full --server github

# 完全モード - Notionサーバーに接続
uv run client.py --mode full --server notion

# 非対話モードでクエリを実行（Slackスレッド返信用）
uv run client.py --mode full --server slack --query "コード検索とタスク作成をしてください" --thread "1620841956.009700" --user "U01ABC123"
```

### 互換性のため、以下の従来のコマンドもサポート（--modeオプションなし、デフォルトで完全モード）

```bash
# 完全モード - Gemini - Slackサーバーに接続
uv run client.py --server slack

# 完全モード - Claude - Slackサーバーに接続
uv run client.py --server slack --model anthropic
```

## 依存関係

- `anthropic`: Claude APIとの通信
- `google-generativeai`: Gemini APIとの通信
- `mcp`: Model Context Protocol実装
- `python-dotenv`: 環境変数の読み込み
- `langchain`: LLMやツールを組み合わせるためのフレームワーク
- `langchain-anthropic`: LangChainとAnthropic Claude APIの連携
- `langchain-google-genai`: LangChainとGoogle Gemini APIの連携
- `langchain-core`: LangChainのコア機能（プロンプト、チェーン、出力処理など）
- `langchain-sql`: LangChainのSQL生成と実行機能
- `sqlalchemy`: データベース操作のためのORMとSQLツールキット
- `mysqlclient`: MySQLデータベースドライバ
- `psycopg2-binary`: PostgreSQLデータベースドライバ

## 拡張性

このクライアントは、新しいMCPサーバーの追加が容易な設計になっています。新しいサービスを追加するには：

1. 対応するスキーマファイルを `schema` ディレクトリに追加
2. 必要に応じて新しいサービスクラスを `services/` に追加
3. 必要に応じてクロスサーバー処理ロジックを拡張
4. ツール呼び出し処理を実装

### データベース機能の設定

データベースへの接続と自然言語クエリ機能を使用するには：

1. 環境変数で接続情報を設定：
   ```
   DB_TYPE=mysql  # mysql, postgresql, sqlite のいずれか
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=username
   DB_PASSWORD=password
   DB_NAME=your_database
   DB_SCHEMA_DESCRIPTION="データベースのテーブルと列に関する説明"  # オプション
   ```

2. サポートされているデータベース：
   - MySQL
   - PostgreSQL
   - SQLite

3. 使用例：
   ```
   # 自然言語でデータベース検索
   uv run client.py --mode simple --model anthropic
   > データベースの全ユーザー数を教えて
   > アクティブなプロジェクトを開始日の新しい順に5件表示して
   > user_idが10のユーザーが担当しているタスクの完了率は？
   ```

### クロスサーバーフロー拡張

クロスサーバーフローのパターンを拡張して、GitHub→Notion→Slackだけでなく、他のサービス組み合わせも実装可能です：

- Notion→GitHub（例：タスクからプルリクエスト作成）
- Slack→GitHub→Slack（例：会話内容からコード生成してPRを作成）
- GitHub→Notion→Email（例：バグ報告と修正タスク作成、担当者へ通知）
- Slack→データベース→Slack（例：会話内容からデータ検索して結果を投稿）

## 参考URL

- [Model Context Protocol](https://modelcontextprotocol.io/quickstart/client)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- [Google Gemini API](https://ai.google.dev/docs)
- [LangChain](https://www.langchain.com/)
- [LangChain ドキュメント](https://python.langchain.com/docs/get_started/introduction)
- [LangChain SQL ドキュメント](https://python.langchain.com/docs/modules/chains/popular/sqlite)
- [SQLAlchemy ドキュメント](https://docs.sqlalchemy.org/)
- [自然言語からSQLへの変換](https://python.langchain.com/docs/use_cases/sql/sql_database)
