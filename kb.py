"""Клавиатуры бота «Гадание на Трёх Рунах».

Callback-контракт (закреплён tests/test_kb.py, используется в bot.py):
draw:pull, draw:new, draw:again, draw:cancel, menu.
"""
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

# --- постоянное меню (клавиатура внизу) ---------------------------------
MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔮 Расклад Три Норны")],
        [KeyboardButton(text="ℹ️ Что за расклад")],
    ],
    resize_keyboard=True,
)

# --- вытягивание руны ---------------------------------------------------
_PULL_TEXTS = {
    "past": "🔮 Вытянуть руну",
    "present": "Вытянуть вторую руну →",
    "future": "Вытянуть третью руну →",
}


def pull_kb(position: str) -> InlineKeyboardMarkup:
    """Кнопка «Вытянуть…» под текущей позицией расклада."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_PULL_TEXTS[position],
                              callback_data="draw:pull")],
    ])


# --- итог расклада ------------------------------------------------------
RESULT = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✦ Новое гадание ✦", callback_data="draw:new")],
    [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")],
])

# --- Предостережение Фрейи ---------------------------------------------
FREYA = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Понятно, подожду", callback_data="draw:cancel")],
    [InlineKeyboardButton(text="Всё равно гадать", callback_data="draw:again")],
])
