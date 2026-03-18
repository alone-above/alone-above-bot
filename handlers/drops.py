"""handlers/drops.py — Дропы (пользователи)"""
import json
from datetime import datetime
from aiogram import Router, F, types
from config import ae
from db import get_active_drops, get_upcoming_drops, get_bot_msg, db_one
from keyboards import btn, kb
from utils import fmt_price

router = Router()


@router.callback_query(F.data == "drops_menu")
async def cb_drops_menu(cb: types.CallbackQuery):
    active   = await get_active_drops()
    upcoming = await get_upcoming_drops()
    header   = await get_bot_msg("drops_header")
    rows     = []

    for d in active:
        rows.append([btn(f"🔥 {d['name']} · {fmt_price(d['price'])}",
                         f"drop_{d['id']}", icon="fire")])
    for d in upcoming:
        start = d["start_at"][:16] if d.get("start_at") else "?"
        rows.append([btn(f"⏳ {d['name']} — старт: {start}",
                         f"drop_{d['id']}", icon="calendar")])
    rows.append([btn("Назад", "shop", icon="back")])

    try:
        await cb.message.edit_text(header, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(header, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("drop_"))
async def cb_drop_detail(cb: types.CallbackQuery):
    did = int(cb.data.split("_")[1])
    d   = await db_one("SELECT * FROM drops WHERE id=$1", (did,))
    if not d:
        await cb.answer("Дроп не найден", show_alert=True)
        return

    now     = datetime.now().isoformat()
    sizes   = json.loads(d["sizes"] or "[]")
    sizes_s = ", ".join(sizes) if sizes else "—"
    is_live = d["start_at"] <= now
    status  = "🔥 Уже в продаже!" if is_live else f"⏳ Старт: {d['start_at'][:16]}"

    text = (
        f"🔥 <b>{d['name']}</b>\n\n"
        f"<blockquote>{d['description']}</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('money')} <b>Цена:</b> <code>{fmt_price(d['price'])}</code>\n"
        f"{ae('size')} <b>Размеры:</b> {sizes_s}\n"
        f"{ae('box')} <b>Статус:</b> {status}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    rows = []
    if is_live and d["stock"] > 0:
        rows.append([btn("Купить", f"buy_drop_{did}", icon="cart")])
    rows.append([btn("Назад", "drops_menu", icon="back")])

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()
