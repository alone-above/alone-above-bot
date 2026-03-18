"""handlers/reviews.py — Показ отзывов на товар"""
from aiogram import Router, F, types
from config import ae
from db import get_reviews
from keyboards import btn, kb

router = Router()


@router.callback_query(F.data.startswith("reviews_"))
async def cb_reviews(cb: types.CallbackQuery):
    pid     = int(cb.data.split("_")[1])
    reviews = await get_reviews(pid, limit=10)
    if not reviews:
        await cb.answer("Отзывов пока нет. Станьте первым! 🙌", show_alert=True)
        return

    stars_map = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}
    text = f"{ae('star')} <b>Отзывы о товаре</b>\n\n━━━━━━━━━━━━━━━━━\n"
    for rv in reviews:
        stars = stars_map.get(rv["rating"], "")
        dt    = rv["created_at"][:10]
        text += f"<b>{stars}</b> <i>{dt}</i>\n{rv['comment']}\n\n"
    text += "━━━━━━━━━━━━━━━━━"

    markup = kb([btn("К товару", f"prod_{pid}", icon="back")])
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()
