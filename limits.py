"""Чистая логика лимитов раскладов — без сети и БД.

Правила (см. docs/superpowers/specs/2026-11-25-limits-stars-design.md):
бесплатно —2 расклада за скользящие7 дней; премиум снимает лимит;
покупка продлевает премиум от его текущего срока.
"""
from config import PREMIUM_DAYS, WEEKLY_FREE_LIMIT

WEEK_SECONDS = 7 * 86400


def is_premium(premium_until: int, now: int) -> bool:
    """Премиум активен, пока now строго меньше срока."""
    return now < premium_until


def can_draw(used: int, premium_until: int, now: int,
             free_limit: int = WEEKLY_FREE_LIMIT) -> bool:
    return is_premium(premium_until, now) or used < free_limit


def remaining(used: int, free_limit: int = WEEKLY_FREE_LIMIT) -> int:
    return max(0, free_limit - used)


def extend_premium(current_until: int, now: int, days: int = PREMIUM_DAYS) -> int:
    """+days к max(now, current_until): активный премиум продлевается от его срока."""
    return max(now, current_until) + days * 86400
