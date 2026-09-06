from sqlalchemy import text

from core import db


def test_engine_pragmas(isolated):
    """Verify that SQLite connection pragmas (WAL, busy timeout, foreign keys) are set."""
    with db.get_engine().connect() as conn:
        wal = conn.execute(text("PRAGMA journal_mode")).scalar()
        timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()

    assert wal.lower() == "wal"
    assert timeout == 5000
    assert fk == 1
