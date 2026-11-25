"""Настройки бота «Гадание на Трёх Рунах».

Локальный запуск: .env рядом с файлом (см. .env.example).
На bothost.ru токен BOT_TOKEN подставляется платформой автоматически.
"""
import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Мини-загрузчик .env (без зависимостей). os.environ имеет приоритет."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(Path(__file__).resolve().parent / ".env")

# --- Telegram -----------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "ВСТАВЬТЕ_ТОКЕН_ОТ_BOTFATHER"

# Локальная подмена DNS для api.telegram.org (пусто = обычный резолвер).
TG_API_IP = os.getenv("TG_API_IP", "")

# Telegram ID владельца: команда /stats отвечает только ему.
ADMIN_ID = int(os.getenv("ADMIN_ID", "3588541"))

# --- Лимиты и Stars -------------------------------------------------------
WEEKLY_FREE_LIMIT = 2   # бесплатных раскладов за скользящие7 дней
PREMIUM_STARS = 30       # цена безлимита на неделю, Telegram Stars
PREMIUM_DAYS = 7         # срок безлимита после оплаты, дней

# --- Хранилище (bothost: /app/data переживает обновления кода из Git) ---
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _probe = DATA_DIR / ".write-test"
    _probe.write_text("ok")
    _probe.unlink()
except Exception:
    # локальный запуск: база рядом с кодом
    DATA_DIR = Path(__file__).resolve().parent / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "runes.db"

# --- Ассеты --------------------------------------------------------------
# Картинка «Предостережение Фрейи» (отправляется с текстом в подписи).
FREYA_IMAGE = Path(__file__).resolve().parent / "assets" / "freya-warning.jpg"
# Нарезанные тайлы рун: rune-01.jpg … rune-24.jpg (порядок = id в runes.ts).
RUNES_DIR = Path(__file__).resolve().parent / "assets" / "runes"
