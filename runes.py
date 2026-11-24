"""Логика выбора рун для расклада «Три Норны».

Только json/random/pathlib — без aiogram и config, чтобы логика
тестировалась без токена. Правила повторяют src/App.tsx (getRandomRune):
без повторов в рамках расклада, 30% шанс перевёрнутой позиции.
"""
import json
import random
from pathlib import Path
from typing import Sequence

RUNES: list[dict] = json.loads(
    (Path(__file__).resolve().parent / "runes.json").read_text(encoding="utf-8")
)


def draw_rune(exclude: Sequence[int]) -> tuple[dict, bool]:
    """Случайная руна из ещё не вытянутых + флаг перевёрнутости."""
    excluded = set(exclude)
    available = [r for r in RUNES if r["id"] not in excluded]
    if not available:
        raise ValueError("все руны уже вытянуты")
    rune = random.choice(available)
    is_reversed = bool(rune.get("reversed")) and random.random() < 0.3
    return rune, is_reversed


def rune_text(rune: dict, position: str, is_reversed: bool) -> str:
    """Текст толкования по позиции (past/present/future).

    Перевёрнутая позиция берёт reversed*-поле, при его отсутствии — обычное.
    """
    if is_reversed:
        return rune.get("reversed" + position.capitalize()) or rune[position]
    return rune[position]


def rune_meaning(rune: dict, is_reversed: bool) -> str:
    """Краткий смысл: перевёрнутый вариант есть не у всех — fallback на обычный."""
    if is_reversed:
        return rune.get("reversedMeaning") or rune["meaning"]
    return rune["meaning"]
