# CLAUDE.md

このファイルは、このリポジトリのコードを扱う際にClaude Code（claude.ai/code）にガイダンスを提供します。

## プロジェクトの概要

このプロジェクトはSlackからメンションが飛んできた際に、そのメンションを処理するためのものです。

メンションの内容によってLLMが何が必要かを判断し、そのLLMに必要な情報を渡します。

1. Slackからメンションを受ける
2. メンションの内容を分析する
3. メンションの内容に応じてLLMを選択する
4. 選択されたLLMに必要な情報を渡す
5. 選択されたLLMが返した回答をSlackに返す and メンションを受けて修正が必要な場合は、Notionに修正依頼を作成する

### Slackへ返信する内容の処理

- Slackへの返信は、メンションを受けたユーザーに対してメンション付きでそのメンションのスレッドに返す
- 返信の内容は、長文になる場合は要約する

### Notionに修正依頼のタスクを作成する

- メンションを受けて修正が必要な場合は、Notionに修正依頼のタスクを作成する
- タスクの内容は、メンションの内容と、そのメンションのスレッドのURL
  - 修正が必要になった原因を記載する
  - Notionへの記載内容はどんな流れで修正すればいいか手順を記載する

## ビルド/テスト/リントコマンド

### Golangのビルド/テスト/リントコマンド

- 依存関係のインストール: `go mod tidy`
- ビルド: `go build`
- テスト: `go test`
- リント: `go fmt`

### TypeScriptのビルド/テスト/リントコマンド

- 依存関係のインストール: `npm install`
- 開発サーバーの起動: `npm run dev`
- プロジェクトのビルド: `npm run build`
- テストの実行: `npm test`
- 単一テストの実行: `npm test -- -t "テスト名"`
- コードのリント: `npm run lint`
- 型チェック: `npm run typecheck`

## コードスタイルガイドライン

- 型安全性のためにTypeScriptを使用
- ESLintとPrettierの設定に従う
- インポート順序: 外部ライブラリ、次に内部モジュール
- 非同期操作にはasync/awaitを使用
- 説明的な変数/関数名（camelCase）を使用
- コンポーネントにはPascalCaseの命名を使用
- try/catchブロックでエラー処理
- 複雑な関数にはJSDocコメントでドキュメント化
- 関数型プログラミングパターンを優先
- 設定には環境変数を使用
- 関数は小さく、単一の責任に焦点を当てる
