"""Run with `python -m app.db.init_db` to (re)create tables. Idempotent."""

from app.config import settings
from app.database import init_db

if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {settings.DB_PATH}")
