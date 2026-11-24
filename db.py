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
                user_id      INTEGER PRIMARY KEY,
                username     TEXT DEFAULT '',
                first_name   TEXT DEFAULT '',
                premium_until INTEGER DEFAULT 0,
                created_at   INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS draws (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                runes     TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchases (
                charge_id  TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                stars      INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
        )
        # Идемпотентная миграция: на bothost уже есть старая таблица users
        # без premium_until — добавляем колонку только если её нет.
        cols = [r[1] for r in conn.execute("pragma table_info(users)")]
        if "premium_until" not in cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN premium_until INTEGER DEFAULT 0"
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


def count_recent_draws(user_id: int, since: int) -> int:
    """Раскладов пользователя строго ПОСЛЕ момента since (скользящее окно)."""
    with _db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE user_id = ? AND created_at > ?",
            (user_id, since),
        ).fetchone()
        return row[0]


# --- премиум и покупки --------------------------------------------------

def get_premium_until(user_id: int) -> int:
    """Срок безлимита (unix);0 — нет строки или премиум не покупался."""
    with _db() as conn:
        row = conn.execute(
            "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row[0]) if row else 0


def set_premium_until(user_id: int, until: int) -> None:
    with _db() as conn:
        conn.execute(
            """INSERT INTO users (user_id, premium_until, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 premium_until = excluded.premium_until""",
            (user_id, until, int(time.time())),
        )


def add_purchase(charge_id: str, user_id: int, stars: int) -> bool:
    """False — такой charge_id уже обработан (дедуп повторной доставки)."""
    with _db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO purchases (charge_id, user_id, stars, created_at)"
            " VALUES (?, ?, ?, ?)",
            (charge_id, user_id, stars, int(time.time())),
        )
        return cur.rowcount == 1


# --- статистика ---------------------------------------------------------

def stats() -> dict:
    with _db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        draws = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        return {"users": users, "draws": draws}
