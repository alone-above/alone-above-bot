"""handlers/catalog.py — Каталог, товарные карточки, галерея"""
import json
from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext

from config import ae
from db import (
    get_categories, get_products, get_product, parse_sizes,
    wish_has, get_avg_rating, get_review_count,
    get_bot_msg, is_banned, log_event, db_one,
)
from keyboards import kb_back, btn, kb
from keyboards.inline import kb_product
from utils import fmt_price

router = Router()


async def show_catalog(bot: Bot, chat_id: int):
    cats   = await get_categories(parent_id=0)
    header = await get_bot_msg("catalog_header")
    if not cats:
        await bot.send_message(
            chat_id,
            f"{ae('folder')} <b>Каталог</b>\n\n<blockquote>Категории пока не добавлены.</blockquote>",
            parse_mode="HTML",
            reply_markup=kb([btn("Назад", "main", icon="back")]),
        )
        return
    rows = [[btn(c["name"], f"cat_{c['id']}", icon="folder")] for c in cats]
    rows.append([btn("Дропы", "drops_menu", icon="fire")])
    rows.append([btn("Назад", "main", icon="back")])
    await bot.send_message(chat_id, header, parse_mode="HTML",
                           reply_markup=kb(*rows))


@router.callback_query(F.data == "shop")
async def cb_shop(cb: types.CallbackQuery, bot: Bot):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫 Вы заблокированы", show_alert=True)
        return
    cats   = await get_categories(parent_id=0)
    header = await get_bot_msg("catalog_header")
    if not cats:
        await cb.answer("Категорий пока нет", show_alert=True)
        return
    rows = [[btn(c["name"], f"cat_{c['id']}", icon="folder")] for c in cats]
    rows.append([btn("Дропы", "drops_menu", icon="fire")])
    rows.append([btn("Назад", "main", icon="back")])
    try:
        await cb.message.edit_text(header, parse_mode="HTML",
                                   reply_markup=kb(*rows))
    except Exception:
        await bot.send_message(cb.from_user.id, header, parse_mode="HTML",
                               reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("cat_"))
async def cb_cat(cb: types.CallbackQuery, bot: Bot):
    cid      = int(cb.data.split("_")[1])
    products = await get_products(cid)
    subcats  = await get_categories(parent_id=cid)

    rows = []
    for sc in subcats:
        rows.append([btn(f"📂 {sc['name']}", f"cat_{sc['id']}", icon="folder")])
    for p in products:
        stock_mark = "" if p["stock"] > 0 else " ✖"
        rows.append([btn(f"{p['name']} — {fmt_price(p['price'])}{stock_mark}",
                         f"prod_{p['id']}", icon="bag")])
    rows.append([btn("Назад", "shop", icon="back")])

    text = f"{ae('folder')} <b>Каталог</b>\n\n<blockquote>Выберите товар:</blockquote>"
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb(*rows))
    except Exception:
        await bot.send_message(cb.from_user.id, text, parse_mode="HTML",
                               reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("prod_"))
async def cb_prod(cb: types.CallbackQuery, bot: Bot):
    pid = int(cb.data.split("_")[1])
    p   = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return

    sizes    = parse_sizes(p)
    avg      = await get_avg_rating(pid)
    rcnt     = await get_review_count(pid)
    in_wish  = await wish_has(cb.from_user.id, pid)

    try:
        gallery = json.loads(p["gallery"] or "[]")
    except Exception:
        gallery = []

    stars = "★" * round(avg) + "☆" * (5 - round(avg)) if avg else "—"
    short = f"  <code>#{p['short_id']}</code>" if p.get("short_id") else ""
    sizes_s = ", ".join(sizes) if sizes else "—"

    text = (
        f"{ae('bag')} <b>{p['name']}</b>{short}\n\n"
        f"<blockquote>{p['description']}</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('money')} <b>Цена:</b> <code>{fmt_price(p['price'])}</code>\n"
        f"{ae('size')} <b>Размеры:</b> {sizes_s}\n"
        f"{ae('box')} <b>Наличие:</b> {'✅ В наличии' if p['stock'] > 0 else '❌ Нет в наличии'}\n"
        f"{ae('star')} <b>Рейтинг:</b> {stars} ({rcnt} отзывов)\n"
        f"━━━━━━━━━━━━━━━━━"
    )

    markup = kb_product(pid, in_wish, len(gallery))
    await log_event("view_product", cb.from_user.id, str(pid))

    # Показываем с медиа если есть обложка
    if p.get("card_file_id"):
        try:
            await cb.message.delete()
        except Exception:
            pass
        try:
            if p["card_media_type"] == "photo":
                await bot.send_photo(cb.from_user.id, p["card_file_id"],
                                     caption=text, parse_mode="HTML", reply_markup=markup)
            elif p["card_media_type"] == "video":
                await bot.send_video(cb.from_user.id, p["card_file_id"],
                                     caption=text, parse_mode="HTML", reply_markup=markup)
            else:
                await bot.send_message(cb.from_user.id, text, parse_mode="HTML",
                                       reply_markup=markup)
            await cb.answer()
            return
        except Exception:
            pass

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await bot.send_message(cb.from_user.id, text, parse_mode="HTML",
                               reply_markup=markup)
    await cb.answer()


# ── Галерея ───────────────────────────────────────────
@router.callback_query(F.data.startswith("gallery_"))
async def cb_gallery(cb: types.CallbackQuery, bot: Bot):
    parts = cb.data.split("_")
    pid   = int(parts[1])
    idx   = int(parts[2])
    p     = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    try:
        gallery = json.loads(p["gallery"] or "[]")
    except Exception:
        gallery = []
    if not gallery:
        await cb.answer("Галерея пуста", show_alert=True)
        return

    idx   = max(0, min(idx, len(gallery) - 1))
    item  = gallery[idx]
    fid   = item["file_id"]
    mt    = item["media_type"]
    total = len(gallery)

    nav = []
    if idx > 0:
        nav.append(btn("◀️", f"gallery_{pid}_{idx-1}", icon="back"))
    nav.append(btn(f"{idx+1}/{total}", "noop"))
    if idx < total - 1:
        nav.append(btn("▶️", f"gallery_{pid}_{idx+1}", icon="link"))

    markup = kb(nav, [btn("К товару", f"prod_{pid}", icon="back")])
    caption = f"🖼 <b>Галерея</b>  {idx+1}/{total}  —  {p['name']}"

    try:
        await cb.message.delete()
    except Exception:
        pass
    try:
        if mt == "photo":
            await bot.send_photo(cb.from_user.id, fid, caption=caption,
                                 parse_mode="HTML", reply_markup=markup)
        elif mt == "video":
            await bot.send_video(cb.from_user.id, fid, caption=caption,
                                 parse_mode="HTML", reply_markup=markup)
        else:
            await bot.send_document(cb.from_user.id, fid, caption=caption,
                                    parse_mode="HTML", reply_markup=markup)
    except Exception:
        await bot.send_message(cb.from_user.id,
                               "⚠️ Не удалось загрузить медиа галереи.",
                               reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: types.CallbackQuery):
    await cb.answer()
