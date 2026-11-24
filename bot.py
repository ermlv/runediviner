"""Бот «Гадание на Трёх Рунах» — расклад «Три Норны» в Telegram.

Сценарий и тексты: docs/superpowers/specs/2026-11-24-rune-bot-design.md,
формулировки — src/App.tsx. Структура хендлеров — по образцу penjoy-bot.
Запуск: python bot.py (polling). Деплой: npm run deploy:bot (см. README.md).
"""
import asyncio
import json
import logging
import time

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, LabeledPrice, Message,
                           PreCheckoutQuery)

import config as C
import db
import kb
import limits
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
async def start_draw(target: Message, state: FSMContext, user_id: int) -> None:
    """Начать расклад с нуля: позиция past, ещё ничего не вытянуто.

    user_id — КЛИКАТЕЛЬ: у сообщения cq.message.from_user это бот, а не
    пользователь. Гейт лимита живёт здесь же — любой старт расклада
    (меню или «Всё равно гадать») обязан его проходить.
    """
    now = int(time.time())
    premium = db.get_premium_until(user_id)
    used = db.count_recent_draws(user_id, now - limits.WEEK_SECONDS)
    if not limits.can_draw(used, premium, now):
        await target.answer(texts.LIMIT_REACHED, reply_markup=kb.BUY_PREMIUM)
        return
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
# Без StateFilter(None): видимые кнопки обязаны отвечать и во время расклада
# (иначе пользователь видит кнопку без реакции — выглядит как поломка).
@router.message(F.text == "🔮 Расклад Три Норны")
async def menu_draw(message: Message, state: FSMContext) -> None:
    await start_draw(message, state, message.from_user.id)


@router.message(F.text == "ℹ️ Что за расклад")
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
        # Подсказка об остатке — только без активного премиума
        if not limits.is_premium(db.get_premium_until(cq.from_user.id),
                                 int(time.time())):
            used = db.count_recent_draws(
                cq.from_user.id, int(time.time()) - limits.WEEK_SECONDS)
            await cq.message.answer(
                texts.after_draw_hint(limits.remaining(used)))
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
    await start_draw(cq.message, state, cq.from_user.id)


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


# ------------------------------------------------ покупка безлимита (Stars)
@router.callback_query(F.data == "pay:stars")
async def pay_stars(cq: CallbackQuery) -> None:
    """Инвойс Telegram Stars:30⭐ → безлимит на неделю."""
    await cq.answer()
    await bot.send_invoice(
        chat_id=cq.message.chat.id,
        title=texts.PREMIUM_INVOICE_TITLE,
        description=texts.PREMIUM_INVOICE_DESCRIPTION,
        payload=str(cq.from_user.id),  # uid плывёт в payload, не в from
        currency="XTR",
        prices=[LabeledPrice(label=texts.PREMIUM_INVOICE_TITLE,
                             amount=C.PREMIUM_STARS)],
    )


@router.pre_checkout_query()
async def pre_checkout(pq: PreCheckoutQuery) -> None:
    """Ответ обязателен за10 секунд, иначе Telegram отменит оплату."""
    ok = pq.currency == "XTR" and pq.total_amount == C.PREMIUM_STARS
    await bot.answer_pre_checkout_query(
        pq.id, ok=ok,
        error_message=None if ok else "Сумма изменилась — попробуйте ещё раз",
    )


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    sp = message.successful_payment
    user_id = int(sp.invoice_payload)
    # Атомарно: покупка + премиум одной транзакцией (db.apply_purchase)
    until = db.apply_purchase(sp.telegram_payment_charge_id, user_id,
                              sp.total_amount, int(time.time()))
    if until is None:
        await message.answer("Эта оплата уже активирована ✓")
        return
    await message.answer(texts.premium_activated(until))


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


@router.message(F.text)
async def any_text(message: Message) -> None:
    await message.answer(texts.MENU_HINT, reply_markup=kb.MENU)


# ------------------------------------------------------------- main
async def main() -> None:
    db.init_db()
    # drop_pending_updates=False: pending successful_payment при рестарте
    # нельзя выбрасывать — пользователь уже заплатил звёзды (см. дизайн).
    await bot.delete_webhook(drop_pending_updates=False)
    # Один апдейт за раз: в draw_pull окно read→sleep(1.5)→write, при
    # параллельной обработке возможен повтор руны и порча FSM-состояния.
    await dp.start_polling(bot, tasks_concurrency_limit=1)


if __name__ == "__main__":
    asyncio.run(main())
