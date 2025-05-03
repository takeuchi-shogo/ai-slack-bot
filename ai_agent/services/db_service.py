import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from config import settings

logger = logging.getLogger(__name__)


class DBService:
    """データベース操作サービス"""

    def __init__(self):
        self.pool = None
        self.test_mode = settings.TEST_MODE

    async def initialize(self) -> None:
        """
        データベース接続プールを初期化する
        """
        if self.test_mode:
            logger.info("テストモードのため、データベース接続をスキップします")
            return

        try:
            self.pool = await asyncpg.create_pool(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
            )
            logger.info(
                f"データベース接続プールを初期化しました: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            )
        except Exception as e:
            logger.error(f"データベース接続プール初期化エラー: {e}")
            raise

    async def close(self) -> None:
        """
        データベース接続プールを閉じる
        """
        if self.pool:
            await self.pool.close()
            logger.info("データベース接続プールを閉じました")

    async def extract_parameters_from_query(self, query: str) -> Tuple[str, List[str]]:
        """
        パラメータ化された文字列を標準的なSQLに変換する

        Args:
            query: SQLクエリ文字列（例: "SELECT * FROM users WHERE name = :name AND age > :age"）

        Returns:
            変換されたクエリとパラメータ名のリストのタプル
        """
        # :name 形式のパラメータを $1, $2, ... 形式に変換
        param_pattern = r":(\w+)"
        param_matches = re.findall(param_pattern, query)
        param_names = []

        # パラメータ名が重複している場合、最初の出現のみをリストに追加
        for name in param_matches:
            if name not in param_names:
                param_names.append(name)

        # クエリ変換
        converted_query = query
        for i, name in enumerate(param_names, 1):
            # パラメータ名をプレースホルダーに置き換え
            converted_query = re.sub(f":{name}\\b", f"${i}", converted_query)

        return converted_query, param_names

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        SQLクエリを実行する

        Args:
            query: 実行するSQLクエリ
            params: クエリパラメータ辞書（オプション）

        Returns:
            実行結果を含む辞書
        """
        if self.test_mode:
            # テストモードではモックデータを返す
            logger.info(f"[テストモード] クエリ実行: {query}")
            return {
                "success": True,
                "query": query,
                "rows": [{"id": 1, "name": "テストデータ"}],
                "row_count": 1,
            }

        if not self.pool:
            try:
                await self.initialize()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"データベース接続エラー: {str(e)}",
                    "query": query,
                }

        async with self.pool.acquire() as conn:
            try:
                # パラメータが辞書形式で渡された場合、変換する
                param_values = []
                if params:
                    # パラメータ化されたクエリを変換
                    (
                        converted_query,
                        param_names,
                    ) = await self.extract_parameters_from_query(query)
                    # パラメータ値を順番通りに設定
                    param_values = [params.get(name) for name in param_names]
                    query = converted_query

                # クエリの種類を判断
                query_type = self._determine_query_type(query)

                if query_type == "SELECT":
                    # SELECT クエリの場合
                    rows = await conn.fetch(query, *param_values)
                    return {
                        "success": True,
                        "query": query,
                        "rows": [dict(row) for row in rows],
                        "row_count": len(rows),
                    }
                else:
                    # その他のクエリ（INSERT, UPDATE, DELETE など）
                    result = await conn.execute(query, *param_values)
                    return {
                        "success": True,
                        "query": query,
                        "result": result,
                    }

            except Exception as e:
                logger.error(f"クエリ実行エラー: {e}, クエリ: {query}")
                return {
                    "success": False,
                    "error": str(e),
                    "query": query,
                }

    def _determine_query_type(self, query: str) -> str:
        """
        SQLクエリの種類（SELECT, INSERT, UPDATE, DELETE）を判断する

        Args:
            query: 判断するSQLクエリ

        Returns:
            クエリの種類
        """
        # 先頭の空白を削除して最初のキーワードを取得
        cleaned_query = re.sub(r"^\s+", "", query)
        first_word = cleaned_query.split(" ")[0].upper()

        if first_word == "SELECT":
            return "SELECT"
        elif first_word in ["INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"]:
            return first_word
        else:
            return "UNKNOWN"

    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        指定されたテーブルのスキーマ情報を取得する

        Args:
            table_name: スキーマを取得するテーブル名

        Returns:
            テーブルスキーマ情報
        """
        if self.test_mode:
            # テストモードではモックデータを返す
            logger.info(f"[テストモード] テーブルスキーマ取得: {table_name}")
            return {
                "success": True,
                "table_name": table_name,
                "columns": [
                    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
                    {
                        "column_name": "name",
                        "data_type": "character varying",
                        "is_nullable": "YES",
                    },
                    {
                        "column_name": "created_at",
                        "data_type": "timestamp",
                        "is_nullable": "NO",
                    },
                ],
            }

        if not self.pool:
            try:
                await self.initialize()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"データベース接続エラー: {str(e)}",
                    "table_name": table_name,
                }

        async with self.pool.acquire() as conn:
            try:
                # PostgreSQLのinformation_schemaからテーブル情報を取得
                schema_query = """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = $1
                ORDER BY ordinal_position;
                """
                columns = await conn.fetch(schema_query, table_name)

                if not columns:
                    return {
                        "success": False,
                        "error": f"テーブル '{table_name}' が存在しません",
                        "table_name": table_name,
                    }

                return {
                    "success": True,
                    "table_name": table_name,
                    "columns": [dict(column) for column in columns],
                }

            except Exception as e:
                logger.error(f"テーブルスキーマ取得エラー: {e}, テーブル: {table_name}")
                return {
                    "success": False,
                    "error": str(e),
                    "table_name": table_name,
                }

    async def list_tables(self) -> Dict[str, Any]:
        """
        データベース内のテーブル一覧を取得する

        Returns:
            テーブル一覧
        """
        if self.test_mode:
            # テストモードではモックデータを返す
            logger.info("[テストモード] テーブル一覧取得")
            return {
                "success": True,
                "tables": ["users", "products", "orders"],
            }

        if not self.pool:
            try:
                await self.initialize()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"データベース接続エラー: {str(e)}",
                }

        async with self.pool.acquire() as conn:
            try:
                # PostgreSQLのpublic schemaのテーブル一覧を取得
                tables_query = """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = 'public';
                """
                tables = await conn.fetch(tables_query)

                return {
                    "success": True,
                    "tables": [table["tablename"] for table in tables],
                }

            except Exception as e:
                logger.error(f"テーブル一覧取得エラー: {e}")
                return {
                    "success": False,
                    "error": str(e),
                }
