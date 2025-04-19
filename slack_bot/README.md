# Slack Bot

このモジュールは、Slackからのメンションを受け取り、ElasticMQキューに追加するSlack Botです。

## 機能概要

- Slack Socket Mode APIを使用したリアルタイムイベント処理
- ElasticMQへのメッセージ送信機能
- 設定管理機能（Viper使用）

## アーキテクチャ

Slack BotはSocket Mode APIを使用してSlackからのメンションをリアルタイムに受信し、それをElasticMQキューに追加します。その後、AI Agentがキューからメッセージを取得して処理を行います。

```mermaid
sequenceDiagram
    participant User
    participant Slack
    participant Bot as Slack Bot (Go)
    participant Queue as ElasticMQ
    
    User->>Slack: メンション送信
    Slack->>Bot: リアルタイムイベント
    Bot->>Bot: イベント処理
    Bot->>Queue: メッセージ追加
    Bot-->>Slack: 初期応答（処理中...）
```

## セットアップ方法

### 必要条件

- Go 1.16+
- Slack App設定（Socket Mode有効）
- Docker環境（ElasticMQの実行用）

### インストール手順

1. 依存パッケージのインストール

```bash
go mod tidy
```

2. 環境変数の設定

`config/config.example.yml` を `config/config.yml` にコピーして、必要な設定を行います。

```bash
cp config/config.example.yml config/config.yml
# config.ymlを編集してSlackボットトークンなどを設定
```

3. ビルドと実行

```bash
go build -o slack-bot ./cmd
./slack-bot
```

## 設定ファイル

`config/config.yml` には以下の設定が必要です：

```yaml
slack_bot:
  bot_token: "xoxb-your-token"
  app_token: "xapp-your-token"

elasticmq:
  endpoint: "http://localhost:9324"
  queue_name: "slack-mentions"
  region: "us-east-1"
  access_key: "dummy"
  secret_key: "dummy"
```

## イベントハンドリング

現在サポートしているイベント：

- `app_mention`: Botがメンションされたときに発生するイベント

## 開発ガイド

- `cmd/main.go`: メインエントリポイント
- `config/`: 設定管理
- `internal/`: 内部ロジック

## トラブルシューティング

- Socket Mode接続エラー: Slack App設定でSocket Modeが有効になっているか確認してください
- ElasticMQ接続エラー: Dockerが起動しているか、エンドポイントが正しいか確認してください
