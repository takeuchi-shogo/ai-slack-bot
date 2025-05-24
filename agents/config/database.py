import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


# データベース設定
class DBType(Enum):
    """サポートされているデータベースの種類"""

    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


# データベース接続情報
DB_TYPE = DBType(os.getenv("DB_TYPE", "mysql"))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "default_db")


# データベース接続URL
def get_db_url():
    """データベースの接続URLを取得"""
    if DB_TYPE == DBType.MYSQL:
        return f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif DB_TYPE == DBType.POSTGRESQL:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif DB_TYPE == DBType.SQLITE:
        return f"sqlite:///{DB_NAME}"
    else:
        raise ValueError(f"Unsupported database type: {DB_TYPE}")
