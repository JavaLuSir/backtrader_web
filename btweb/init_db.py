from __future__ import annotations

from .db import engine
from .models import Base


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def main() -> None:
    init_db()
    print("OK: tables ensured.")


if __name__ == "__main__":
    main()

