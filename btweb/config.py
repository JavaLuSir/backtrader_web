from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    strategies_dir: Path
    static_dir: Path
    auto_init_db: bool


def load_settings() -> Settings:
    # .env 只在本地开发时使用；生产环境直接用环境变量即可
    load_dotenv(override=False)

    repo_root = Path(__file__).resolve().parent.parent

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        host = os.getenv("DB_HOST", "192.168.1.10")
        port = os.getenv("DB_PORT", "3306")
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "Lx@12345678")
        db_name = os.getenv("DB_NAME", "stock")

        database_url = (
            f"mysql+pymysql://{user}:{quote_plus(password)}@{host}:{port}/{db_name}"
            "?charset=utf8mb4"
        )

    strategies_dir = Path(os.getenv("STRATEGIES_DIR", str(repo_root / "strategies"))).resolve()
    static_dir = Path(os.getenv("STATIC_DIR", str(repo_root / "static"))).resolve()
    auto_init_db = os.getenv("AUTO_INIT_DB", "1").strip() not in {"0", "false", "False"}

    return Settings(
        database_url=database_url,
        strategies_dir=strategies_dir,
        static_dir=static_dir,
        auto_init_db=auto_init_db,
    )

