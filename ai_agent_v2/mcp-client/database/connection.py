"""
データベース接続モジュール

SQLAlchemyを使用してデータベースへの接続を管理します。
様々なデータベース（MySQL、PostgreSQL、SQLite）に対応しています。
"""

import logging
from typing import Dict, List

from config import DB_SCHEMA_DESCRIPTION, get_db_url
from langchain_community.utilities import SQLDatabase
from sqlalchemy import MetaData, create_engine, inspect, text

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    データベース接続を管理するクラス

    SQLAlchemyとLangChainのSQLDatabaseを組み合わせて
    データベースへのアクセスと操作を提供します。
    """

    def __init__(self):
        """DatabaseConnectionの初期化"""
        self._engine = None
        self._connection = None
        self._metadata = None
        self._inspector = None
        self._langchain_db = None
        self._tables_info = None

    async def connect(self) -> bool:
        """
        データベースに接続する

        Returns:
            bool: 接続成功時はTrue、失敗時はFalse
        """
        try:
            db_url = get_db_url()
            print(f"データベースURL: {db_url}")
            self._engine = create_engine(db_url)
            self._connection = self._engine.connect()
            self._metadata = MetaData()
            self._metadata.reflect(bind=self._engine)
            self._inspector = inspect(self._engine)

            # LangChain SQLDatabaseインスタンスを作成
            self._langchain_db = SQLDatabase.from_uri(db_url)

            logger.info(f"データベースに接続しました: {db_url}")
            return True
        except Exception as e:
            logger.error(f"データベース接続エラー: {str(e)}")
            return False

    async def disconnect(self) -> None:
        """データベース接続を閉じる"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("データベース接続を閉じました")

    def get_langchain_db(self) -> SQLDatabase:
        """
        LangChain SQLDatabaseインスタンスを取得

        Returns:
            SQLDatabase: LangChainのSQLDatabaseインスタンス
        """
        if not self._langchain_db:
            raise ValueError(
                "データベースに接続されていません。先にconnect()を呼び出してください。"
            )
        return self._langchain_db

    def get_table_names(self) -> List[str]:
        """
        テーブル名のリストを取得

        Returns:
            List[str]: データベース内のテーブル名のリスト
        """
        if not self._inspector:
            raise ValueError(
                "データベースに接続されていません。先にconnect()を呼び出してください。"
            )
        return self._inspector.get_table_names()

    def get_table_info(self, table_name: str) -> Dict:
        """
        指定したテーブルの情報を取得

        Args:
            table_name: 情報を取得するテーブル名

        Returns:
            Dict: テーブル情報（カラム、制約など）
        """
        if not self._inspector:
            raise ValueError(
                "データベースに接続されていません。先にconnect()を呼び出してください。"
            )

        columns = self._inspector.get_columns(table_name)
        pk = self._inspector.get_pk_constraint(table_name)
        fks = self._inspector.get_foreign_keys(table_name)

        return {
            "name": table_name,
            "columns": columns,
            "primary_key": pk,
            "foreign_keys": fks,
        }

    def get_schema_info(self) -> str:
        """
        データベーススキーマの説明を取得（LLM用）

        Returns:
            str: データベーススキーマの説明
        """
        if self._tables_info is None:
            self._tables_info = self._generate_schema_info()

        return DB_SCHEMA_DESCRIPTION + "\n" + self._tables_info

    def _generate_schema_info(self) -> str:
        """
        テーブル情報に基づいてスキーマ情報を生成

        Returns:
            str: 生成されたスキーマ情報
        """
        if not self._inspector:
            raise ValueError(
                "データベースに接続されていません。先にconnect()を呼び出してください。"
            )

        tables = self.get_table_names()
        schema_info = []

        for table in tables:
            columns = self._inspector.get_columns(table)
            column_details = []

            for col in columns:
                col_type = str(col["type"])
                constraints = []

                if col.get("nullable") is False:
                    constraints.append("NOT NULL")
                if col.get("default") is not None:
                    constraints.append(f"DEFAULT {col['default']}")

                constraint_str = " ".join(constraints) if constraints else ""
                column_details.append(f"- {col['name']}: {col_type} {constraint_str}")

            schema_info.append(f"テーブル: {table}")
            schema_info.append("\nカラム:")
            schema_info.append("\n".join(column_details))
            schema_info.append("\n")

        return "\n".join(schema_info)

    async def execute_raw_query(self, query: str) -> List[Dict]:
        """
        生のSQLクエリを実行し、結果を辞書のリストとして返す

        Args:
            query: 実行するSQLクエリ

        Returns:
            List[Dict]: クエリ結果
        """
        if not self._connection:
            raise ValueError(
                "データベースに接続されていません。先にconnect()を呼び出してください。"
            )

        try:
            result = self._connection.execute(text(query))
            columns = result.keys()
            rows = result.fetchall()

            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"クエリ実行エラー: {str(e)}")
            raise
