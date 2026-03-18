"""handlers/orders.py — Мои заказы, детали, подтверждение, отзыв"""
from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ae, MANAGER_ID
from db import (
    get_user_orders, get_order, get_order_history, get_order_note,
    set_order_status, add_review, get_product,
)
from keyboards import kb_main, kb_back, btn, kb
from utils import fmt_price, order_status_text

router = Router()


class ReviewSt(StatesGroup):
    rating  = State()
    comment = State()


@router.callback_query(F.data == "my_orders")
async def cb_my_orders(cb: types.CallbackQuery):
    orders = await get_user_orders(cb.from_user.id)
    if not orders:
        await cb.answer("Заказов пока нет", show_alert=True)
        return
    rows = []
    for o in orders:
        icon = {
            "processing": "🔄", "china": "✈️", "arrived": "📦",
            "delivered": "🚚", "confirmed": "✅",
        }.get(o["status"], "❓")
        label = f"{icon} #{o['id']} {o['pname'][:15]} ({o['size']}) — {o['created_at'][:10]}"
        rows.append([btn(label, f"myorder_{o['id']}")])
    rows.append([btn("Назад", "profile_view", icon="back")])
    text = (
        f"{ae('archive')} <b>Мои заказы</b>\n\n"
        f"<blockquote>Нажмите на заказ для подробностей:</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("myorder_"))
async def cb_myorder_detail(cb: types.CallbackQuery):
    oid   = int(cb.data.split("_")[1])
    order = await get_order(oid)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Заказ не найден", show_alert=True)
        return

    product = await get_product(order["product_id"])
    history = await get_order_history(oid)
    note    = await get_order_note(oid)

    promo_line = ""
    if order.get("promo_code"):
        promo_line = f"🎟 <b>Промокод:</b> <code>{order['promo_code']}</code>\n"

    note_line = f"\n📝 <b>Ваше примечание:</b>\n<i>{note}</i>\n" if note else ""

    status_labels = {
        "processing": "🔄 В обработке",
        "china":      "✈️ Едет из Китая",
        "arrived":    "📦 Прибыло",
        "delivered":  "🚚 Передано",
        "confirmed":  "✅ Подтверждено покупателем",
    }
    history_lines = "\n📋 <b>История статусов:</b>\n"
    for h in history:
        history_lines += f"  • {status_labels.get(h['status'], h['status'])}  <i>{h['created_at'][:16]}</i>\n"

    text = (
        f"📋 <b>Заказ #{oid}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('box')} <b>Товар:</b> {product['name'] if product else '—'}\n"
        f"{ae('size')} <b>Размер:</b> {order['size']}\n"
        f"{ae('money')} <b>Сумма:</b> {fmt_price(order['price'])}\n"
        f"{promo_line}"
        f"💳 <b>Оплата:</b> {order['method']}\n"
        f"🔄 <b>Статус:</b> {order_status_text(order['status'])}\n"
        f"{ae('cal')} {order['created_at'][:16]}\n"
        f"━━━━━━━━━━━━━━━━━"
        f"{note_line}"
        f"{history_lines}"
    )

    rows = []
    if order["status"] == "delivered":
        rows.append([btn("Подтвердить получение",
                         f"confirm_order_{oid}", icon="ok")])
    rows.append([btn("Пожаловаться на товар",
                     f"complaint_order_{oid}", icon="no")])
    rows.append([btn("Назад", "my_orders", icon="back")])

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


# ── Подтверждение получения ───────────────────────────
@router.callback_query(F.data.startswith("confirm_order_"))
async def cb_confirm_order(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
    oid   = int(cb.data.split("_")[-1])
    order = await get_order(oid)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Заказ не найден", show_alert=True)
        return

    await set_order_status(oid, "confirmed")
    try:
        await bot.send_message(MANAGER_ID,
                               f"✅ <b>Заказ #{oid} подтверждён покупателем.</b>",
                               parse_mode="HTML")
    except Exception:
        pass

    await state.update_data(review_oid=oid, review_pid=order["product_id"])
    await state.set_state(ReviewSt.rating)

    try:
        await cb.message.edit_text(
            f"{ae('confetti')} <b>Спасибо за подтверждение!</b>\n\n"
            f"<blockquote>Оцените товар от 1 до 5 звёзд:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb([btn(str(i), f"rating_{i}") for i in range(1, 6)]),
        )
    except Exception:
        pass
    await cb.answer()


# ── Отзыв ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("rating_"), ReviewSt.rating)
async def cb_rating(cb: types.CallbackQuery, state: FSMContext):
    rating    = int(cb.data.split("_")[1])
    stars_map = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}
    await state.update_data(rating=rating)
    await state.set_state(ReviewSt.comment)
    try:
        await cb.message.edit_text(
            f"Оценка: <b>{stars_map[rating]}</b>\n\n"
            f"<blockquote>Напишите ваш отзыв о товаре:</blockquote>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(ReviewSt.comment)
async def proc_review_comment(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    await add_review(msg.from_user.id, d["review_pid"], d["review_oid"],
                     d["rating"], msg.text)
    await msg.answer(
        f"{ae('star')} <b>Спасибо за отзыв!</b>\n\n"
        f"<blockquote>Ваш отзыв поможет другим покупателям.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
