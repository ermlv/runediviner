"""SQLite-хранилище бота: пользователи и расклады.

База создаётся программно при старте. На bothost лежит в /app/data
(переживает обновления кода), локально — в bot/data/ (см. config.py).
"""
import sqlite3
import time
from contextlib import contextmanager

import config as C


@contextmanager
def _db():
    conn = sqlite3.connect(str(C.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS draws (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                runes     TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
        )


# --- пользователи -------------------------------------------------------

def upsert_user(user_id: int, username: str, first_name: str) -> None:
    with _db() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, first_name, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username = excluded.username,
                 first_name = excluded.first_name""",
            (user_id, username, first_name, int(time.time())),
        )


# --- расклады -----------------------------------------------------------

def add_draw(user_id: int, runes_json: str) -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO draws (user_id, runes, created_at) VALUES (?, ?, ?)",
            (user_id, runes_json, int(time.time())),
        )
        return cur.lastrowid


# --- статистика ---------------------------------------------------------

def stats() -> dict:
    with _db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        draws = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        return {"users": users, "draws": draws}
