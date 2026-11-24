"""Бот «Гадание на Трёх Рунах» — расклад «Три Норны» в Telegram.

Сценарий и тексты: docs/superpowers/specs/2026-11-24-rune-bot-design.md,
формулировки — src/App.tsx. Структура хендлеров — по образцу penjoy-bot.
Запуск: python bot.py (polling). Деплой: npm run deploy:bot (см. README.md).
"""
import asyncio
import json
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config as C
import db
import kb
import runes
import texts

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("runediviner")

# Локальный воркaround: если задан TG_API_IP, резолвер api.telegram.org
# подменяется на этот IP (см. tgip.py; на bothost переменная не задаётся).
if C.TG_API_IP:
    import tgip
    tgip.install("api.telegram.org", C.TG_API_IP)
    log.info("DNS-подмена: api.telegram.org → %s", C.TG_API_IP)

bot = Bot(token=C.BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

ORDER = ("past", "present", "future")


# ------------------------------------------------------------------ FSM
class DrawSG(StatesGroup):
    drawing = State()


# ------------------------------------------------------------- helpers
async def start_draw(target: Message, state: FSMContext) -> None:
    """Начать расклад с нуля: позиция past, ещё ничего не вытянуто."""
    await state.set_state(DrawSG.drawing)
    await state.update_data(drawn=[], pos="past")
    await target.answer(texts.draw_prompt("past"),
                        reply_markup=kb.pull_kb("past"))


# ------------------------------------------------------------- /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    db.upsert_user(message.from_user.id, message.from_user.username or "",
                   message.from_user.first_name or "")
    await state.clear()
    await message.answer(texts.WELCOME, reply_markup=kb.MENU)


# ------------------------------------------------------------- меню
@router.message(StateFilter(None), F.text == "🔮 Расклад Три Норны")
async def menu_draw(message: Message, state: FSMContext) -> None:
    await start_draw(message, state)


@router.message(StateFilter(None), F.text == "ℹ️ Что за расклад")
async def menu_info(message: Message) -> None:
    await message.answer(texts.INFO_TEXT)


# ------------------------------------------------------------- расклад
@router.callback_query(F.data == "draw:pull", DrawSG.drawing)
async def draw_pull(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    data = await state.get_data()
    pos = data.get("pos", "past")
    drawn = list(data.get("drawn", []))

    # ритуал «вытягивания» — как в приложении: индикатор + пауза
    await cq.message.bot.send_chat_action(chat_id=cq.message.chat.id,
                                          action="typing")
    await asyncio.sleep(1.5)

    rune, is_reversed = runes.draw_rune([d["rune"]["id"] for d in drawn])
    drawn.append({"rune": rune, "position": pos, "is_reversed": is_reversed})

    if pos == "future":
        # последняя руна: раскрытие без кнопки, затем итог
        await cq.message.answer(texts.reveal_message(rune, pos, is_reversed))
        payload = [{"id": d["rune"]["id"], "position": d["position"],
                    "is_reversed": d["is_reversed"]} for d in drawn]
        db.add_draw(cq.from_user.id, json.dumps(payload, ensure_ascii=False))
        await cq.message.bot.send_chat_action(chat_id=cq.message.chat.id,
                                              action="typing")
        await asyncio.sleep(1.0)
        await cq.message.answer(texts.result_message(drawn),
                                reply_markup=kb.RESULT)
        await state.clear()
        return

    nxt = ORDER[ORDER.index(pos) + 1]
    await state.update_data(drawn=drawn, pos=nxt)
    await cq.message.answer(texts.reveal_message(rune, pos, is_reversed),
                            reply_markup=kb.pull_kb(nxt))


# --------------------------------------------------- новое гадание + Фрейя
@router.callback_query(F.data == "draw:new")
async def draw_new(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.answer(texts.FREYA_WARNING, reply_markup=kb.FREYA)


@router.callback_query(F.data == "draw:again")
async def draw_again(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await start_draw(cq.message, state)


@router.callback_query(F.data == "draw:cancel")
async def draw_cancel(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.clear()
    await cq.message.answer("Хорошо, буду ждать. ✨\n" + texts.MENU_HINT,
                            reply_markup=kb.MENU)


@router.callback_query(F.data == "menu")
async def cb_menu(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.clear()
    await cq.message.answer("Главное меню 👇", reply_markup=kb.MENU)


# ------------------------------------------------------------- админ
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user.id != C.ADMIN_ID:
        return
    s = db.stats()
    await message.answer(
        f"📊 Расклады: пользователей {s['users']}, раскладов {s['draws']}"
    )


# ------------------------------------------- страховка от «мёртвых» кнопок
@router.callback_query()
async def any_callback(cq: CallbackQuery) -> None:
    """Любая неизвестная кнопка (в т.ч. из старого расклада): ответ обязателен,
    иначе Telegram крутит спиннер. Ловит и draw:pull без состояния FSM."""
    await cq.answer("Кнопка устарела")
    await cq.message.answer(texts.STALE_HINT, reply_markup=kb.MENU)


@router.message(StateFilter(None), F.text)
async def any_text(message: Message) -> None:
    await message.answer(texts.MENU_HINT, reply_markup=kb.MENU)


# ------------------------------------------------------------- main
async def main() -> None:
    db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)  # polling, не webhook
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
