# データベースマイグレーション

このディレクトリはSlack Botアプリケーション用のデータベースマイグレーションファイルを含んでいます。

## マイグレーションツール

以下の2つのマイグレーションツールを使用しています：

1. **Atlas**: スキーマ定義からマイグレーションを生成するためのツール
2. **golang-migrate**: 生成されたマイグレーションを実行するためのツール

## ディレクトリ構造

- `schema.hcl`: メインのHCLスキーマ定義（Atlasはこれをソースとして使用）
- `atlas.hcl`: Atlas設定ファイル
- `Dockerfile`: マイグレーション実行用のコンテナ定義
- `schema/`: Atlas生成のマイグレーションファイルディレクトリ

## Atlasを使った正しいワークフロー

Atlasの正しい使い方は、SQLファイルを手動で書くのではなく、スキーマ定義からマイグレーションを生成することです：

### 1. スキーマ定義を更新

まず`schema.hcl`ファイルでスキーマを定義/更新します：

```hcl
table "example_table" {
  schema  = schema.slackbot
  engine  = "InnoDB"
  charset = "utf8mb4"
  collate = "utf8mb4_unicode_ci"
  
  column "id" {
    type     = char(26)
    null     = false
    comment  = "ULID primary key"
  }
  
  // 他のカラム定義...
  
  primary_key {
    columns = [column.id]
  }
  
  index "idx_example_table_name" {
    columns = [column.name]
  }
}
```

### 2. マイグレーションファイルを生成

Atlasを使用してスキーマの変更からマイグレーションファイルを自動生成します：

```bash
# マイグレーションファイルの生成
docker compose run --rm migrations atlas migrate diff --env default --to "add_example_table"
```

これにより、`schema/`ディレクトリに新しいマイグレーションファイルが生成されます。

### 3. マイグレーションの実行

生成されたマイグレーションを実行します：

```bash
# マイグレーションを適用
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" up
```

## マイグレーションの自動実行

マイグレーションはDocker Compose起動時に自動的に実行されます：

```bash
docker compose up
```

## Atlas CLIの主要コマンド

スキーマ管理のための重要なAtlasコマンド：

```bash
# 現在のDBとスキーマ定義の差分を確認
docker compose run --rm migrations atlas schema diff --env default

# スキーマの検証
docker compose run --rm migrations atlas schema verify --env default

# 変更のマイグレーションファイルを生成
docker compose run --rm migrations atlas migrate diff --env default --to "description_of_change"

# マイグレーションを生成せずにスキーマ差分をDDLとして表示
docker compose run --rm migrations atlas schema inspect --env default

# スキーマハッシュの取得（CI/CDで変更検出用）
docker compose run --rm migrations atlas schema hash --env default
```

## golang-migrateコマンド

マイグレーションファイル適用のためのコマンド：

```bash
# マイグレーションを進める
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" up

# マイグレーションを1つ戻す
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" down 1

# マイグレーションのステータス確認
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" version
```

## トラブルシューティング

### マイグレーションが失敗する場合

1. スキーマ定義（schema.hcl）に誤りがないか確認してください
2. 生成されたマイグレーションファイルに問題がないか確認してください
3. 既存のデータとの整合性を確認してください

### スキーマ適用フローのリセット

```bash
# マイグレーションをリセットする場合
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" drop
docker compose run --rm migrations migrate -path ./schema -database "mysql://user:password@tcp(mysql:3306)/slackbot" up
```

### データベースに直接接続する方法

```bash
# MySQLコンテナに接続
docker compose exec mysql mysql -u user -ppassword slackbot

# 特定のテーブルの構造を確認
DESCRIBE slack_mentions;

# マイグレーション履歴テーブルを確認
SELECT * FROM schema_migrations;
```

## 現在のテーブル構造

### slack_mentions テーブル

| カラム名     | 型           | 説明                    |
|------------|--------------|------------------------|
| id         | CHAR(26)     | ULID主キー              |
| type       | VARCHAR(255) | メンションタイプ         |
| user_id    | VARCHAR(255) | SlackユーザーID         |
| channel_id | VARCHAR(255) | SlackチャネルID         |
| text       | TEXT         | メンションテキスト       |
| timestamp  | DATETIME     | Slackイベントタイムスタンプ |
| event_time | DATETIME     | Slackイベント時間       |
| created_at | DATETIME     | レコード作成時間         |
| updated_at | DATETIME     | レコード更新時間         |
| deleted_at | DATETIME     | 論理削除時間            |

### slack_mention_responses テーブル

| カラム名     | 型           | 説明                    |
|------------|--------------|------------------------|
| id         | CHAR(26)     | ULID主キー              |
| mention_id | CHAR(26)     | slack_mentions.idへの参照 |
| content    | TEXT         | レスポンス内容           |
| status     | VARCHAR(50)  | レスポンスのステータス   |
| sent_at    | DATETIME     | 送信時間                |
| created_at | DATETIME     | レコード作成時間         |
| updated_at | DATETIME     | レコード更新時間         |
| deleted_at | DATETIME     | 論理削除時間            |
