"""handlers/admin.py — Полная панель администратора"""
import io
import json
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    ae, ADMIN_IDS, MANAGER_ID, SHOP_NAME,
    ROLES, PROMO_TYPES, NAV_CALLBACKS,
    BOT_MSG_KEYS_LABELS,
)
from db import (
    # Статистика
    get_stats, db_all, db_one, db_run,
    # Пользователи
    get_user, get_all_users, ban_user, unban_user, is_banned,
    get_user_role, set_user_role,
    # Каталог
    get_categories, get_all_categories, get_category,
    add_category, del_category,
    get_products, get_product, add_product,
    update_product_field, del_product, parse_sizes,
    # Заказы
    get_order, set_order_status,
    # Промокоды
    get_all_promos, create_promo, delete_promo, get_promo_by_id,
    # Медиа / настройки
    set_media, get_setting, set_setting,
    get_bot_msg, set_bot_msg,
    # Партнёры
    get_partner, update_partner_bonuses,
    # Дропы
    get_all_drops_admin, add_drop, del_drop,
    # Лог
    log_event, all_user_ids,
)
from keyboards import kb_admin_back, kb_back, btn, kb, kb_admin
from utils import fmt_price, fmt_dt, order_status_text

router = Router()


# ════════════════════════════════════════════════════
#  FSM-состояния админки
# ════════════════════════════════════════════════════
class AdminSt(StatesGroup):
    broadcast          = State()
    set_media_file     = State()
    add_cat_name       = State()
    add_prod_name      = State()
    add_prod_desc      = State()
    add_prod_price     = State()
    add_prod_sizes     = State()
    add_prod_stock     = State()
    add_prod_seller_ph = State()
    add_prod_seller_un = State()
    add_prod_card      = State()
    add_prod_gallery   = State()
    add_drop_name      = State()
    add_drop_desc      = State()
    add_drop_price     = State()
    add_drop_sizes     = State()
    add_drop_stock     = State()
    add_drop_start_at  = State()
    add_drop_card      = State()
    edit_shop_info     = State()
    set_custom_status  = State()
    promo_code         = State()
    promo_type         = State()
    promo_value        = State()
    promo_description  = State()
    promo_max_uses     = State()
    ban_user_id        = State()
    msg_user_id        = State()
    msg_user_text      = State()
    edit_prod_field    = State()
    edit_prod_value    = State()
    role_user_id       = State()
    partner_bonus_new  = State()
    partner_bonus_rep  = State()
    bot_msg_text       = State()
    subcat_parent      = State()
    subcat_name        = State()


def admin_guard(uid: int) -> bool:
    return uid in ADMIN_IDS


# ════════════════════════════════════════════════════
#  Статистика
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    uc, pc, rv, ac, oc, prc, bc, cmp = await get_stats()
    text = (
        f"{ae('chart')} <b>Статистика магазина</b>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('users')} <b>Пользователей:</b> {uc}\n"
        f"{ae('cart')} <b>Покупок всего:</b> {pc}\n"
        f"{ae('cash')} <b>Выручка:</b> {fmt_price(rv)}\n"
        f"{ae('box')} <b>Активных товаров:</b> {ac}\n"
        f"{ae('refresh')} <b>Заказов в работе:</b> {oc}\n"
        f"{ae('promo')} <b>Промокодов:</b> {prc}\n"
        f"{ae('lock')} <b>Заблокировано:</b> {bc}\n"
        f"⚠️ <b>Открытых жалоб:</b> {cmp}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_admin_back())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb_admin_back())
    await cb.answer()


# ════════════════════════════════════════════════════
#  Рассылка
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    await state.set_state(AdminSt.broadcast)
    try:
        await cb.message.edit_text(
            f'{ae("megaphone")} <b>Рассылка</b>\n\n'
            f'<blockquote>Отправьте сообщение для рассылки всем пользователям.\n'
            f'Поддерживается: текст, фото, видео с подписью.</blockquote>',
            parse_mode="HTML",
            reply_markup=kb_back("adm_panel"),
        )
    except Exception:
        await cb.message.answer(
            f'{ae("megaphone")} <b>Рассылка</b>', parse_mode="HTML",
            reply_markup=kb_back("adm_panel"),
        )
    await cb.answer()


@router.message(AdminSt.broadcast)
async def proc_broadcast(msg: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    uids  = await all_user_ids()
    ok    = 0
    fail  = 0
    for uid in uids:
        try:
            if msg.photo:
                await bot.send_photo(uid, msg.photo[-1].file_id,
                                     caption=msg.caption or "",
                                     parse_mode="HTML")
            elif msg.video:
                await bot.send_video(uid, msg.video.file_id,
                                     caption=msg.caption or "",
                                     parse_mode="HTML")
            elif msg.text:
                await bot.send_message(uid, msg.text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # Flood control
    await msg.answer(
        f"{ae('ok')} <b>Рассылка завершена</b>\n\n"
        f"✅ Доставлено: {ok}\n❌ Ошибок: {fail}",
        parse_mode="HTML",
        reply_markup=kb_admin_back(),
    )


# ════════════════════════════════════════════════════
#  Медиа
# ════════════════════════════════════════════════════
MEDIA_KEYS = {
    "main_menu":     "Главное меню",
    "admin_panel":   "Панель администратора",
    "catalog_menu":  "Каталог",
    "support_menu":  "Поддержка",
    "about_menu":    "О магазине",
    "profile_menu":  "Профиль",
}


@router.callback_query(F.data == "adm_media")
async def cb_adm_media(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    rows = [[btn(label, f"setmedia_{key}", icon="file")]
            for key, label in MEDIA_KEYS.items()]
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("file")} <b>Медиа для разделов</b>\n\n'
            f'<blockquote>Выберите раздел для установки обложки:</blockquote>',
            parse_mode="HTML",
            reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(
            f'{ae("file")} <b>Медиа</b>', parse_mode="HTML", reply_markup=kb(*rows)
        )
    await cb.answer()


@router.callback_query(F.data.startswith("setmedia_"))
async def cb_setmedia(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    key = cb.data[len("setmedia_"):]
    await state.update_data(media_key=key)
    await state.set_state(AdminSt.set_media_file)
    label = MEDIA_KEYS.get(key, key)
    try:
        await cb.message.edit_text(
            f'🖼 <b>Медиа для «{label}»</b>\n\n'
            f'<blockquote>Отправьте фото, видео или GIF.\n'
            f'Напишите <b>удалить</b> — убрать медиа.</blockquote>',
            parse_mode="HTML",
            reply_markup=kb_back("adm_media"),
        )
    except Exception:
        await cb.message.answer("🖼 Отправьте медиафайл или напишите «удалить».",
                                reply_markup=kb_back("adm_media"))
    await cb.answer()


@router.message(AdminSt.set_media_file)
async def proc_media_file(msg: types.Message, state: FSMContext):
    d   = await state.get_data()
    key = d.get("media_key", "")
    await state.clear()
    if msg.text and msg.text.strip().lower() in ("удалить", "delete"):
        await db_run("DELETE FROM media_settings WHERE key=$1", (key,))
        from db import _cache_invalidate
        _cache_invalidate(f"media:{key}")
        await msg.answer("✅ Медиа удалено.", reply_markup=kb_admin_back())
        return
    if msg.photo:
        fid, mtype = msg.photo[-1].file_id, "photo"
    elif msg.video:
        fid, mtype = msg.video.file_id, "video"
    elif msg.animation:
        fid, mtype = msg.animation.file_id, "animation"
    else:
        await msg.answer("❌ Поддерживаются: фото, видео, GIF.")
        return
    await set_media(key, mtype, fid)
    await msg.answer(f"✅ Медиа для «{MEDIA_KEYS.get(key, key)}» обновлено!",
                     reply_markup=kb_admin_back())


# ════════════════════════════════════════════════════
#  Категории
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_cats")
async def cb_adm_cats(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    cats = await get_categories(parent_id=0)
    rows = []
    for c in cats:
        subcats = await get_categories(parent_id=c["id"])
        sub_mark = f" ({len(subcats)}↳)" if subcats else ""
        rows.append([
            btn(f"📁 {c['name']}{sub_mark}", f"vcat_{c['id']}", icon="folder"),
            btn("Удалить", f"dcat_{c['id']}", icon="delete"),
        ])
    rows.append([btn("Новая категория",   "add_cat",    icon="add")])
    rows.append([btn("Новая подкатегория", "add_subcat", icon="add")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("folder")} <b>Категории</b>\n\n<blockquote>Управление категориями:</blockquote>',
            parse_mode="HTML",
            reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("folder")} <b>Категории</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data == "add_cat")
async def cb_add_cat(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    await state.update_data(is_subcat=False, subcat_parent_id=0)
    await state.set_state(AdminSt.add_cat_name)
    try:
        await cb.message.edit_text(
            f'{ae("folder")} <b>Новая категория</b>\n\n<blockquote>Введите название:</blockquote>',
            parse_mode="HTML",
            reply_markup=kb_back("adm_cats"),
        )
    except Exception:
        await cb.message.answer(f'{ae("folder")} <b>Новая категория</b>',
                                parse_mode="HTML", reply_markup=kb_back("adm_cats"))
    await cb.answer()


@router.callback_query(F.data == "add_subcat")
async def cb_add_subcat(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    cats = await get_categories(parent_id=0)
    if not cats:
        await cb.answer("Сначала создайте родительскую категорию!", show_alert=True)
        return
    rows = [[btn(c["name"], f"subcat_parent_{c['id']}")] for c in cats]
    rows.append([btn("Назад", "adm_cats", icon="back")])
    try:
        await cb.message.edit_text(
            "📂 <b>Выберите родительскую категорию:</b>",
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer("📂 <b>Выберите категорию</b>",
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("subcat_parent_"))
async def cb_subcat_parent(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    parent_id = int(cb.data.split("_")[2])
    await state.update_data(is_subcat=True, subcat_parent_id=parent_id)
    await state.set_state(AdminSt.add_cat_name)
    try:
        await cb.message.edit_text(
            "📂 <b>Новая подкатегория</b>\n\n<blockquote>Введите название:</blockquote>",
            parse_mode="HTML", reply_markup=kb_back("adm_cats"),
        )
    except Exception:
        await cb.message.answer("📂 Введите название подкатегории:")
    await cb.answer()


@router.message(AdminSt.add_cat_name)
async def proc_cat_name(msg: types.Message, state: FSMContext):
    d         = await state.get_data()
    is_subcat = d.get("is_subcat", False)
    parent_id = d.get("subcat_parent_id", 0)
    await add_category(msg.text.strip(), parent_id=parent_id if is_subcat else 0)
    await state.clear()
    kind = "Подкатегория" if is_subcat else "Категория"
    await msg.answer(f"✅ {kind} добавлена!", reply_markup=kb_admin_back())


@router.callback_query(F.data.startswith("dcat_"))
async def cb_dcat(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    cid = int(cb.data.split("_")[1])
    await del_category(cid)
    await cb.answer("✅ Категория удалена", show_alert=True)
    await cb_adm_cats(cb)


# ════════════════════════════════════════════════════
#  Товары — просмотр и удаление
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_products")
async def cb_adm_products(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    cats  = await get_all_categories()
    rows  = [[btn(f"{'  ↳ ' if c.get('parent_id',0) else ''}{c['name']}",
                  f"apcat_{c['id']}")] for c in cats]
    rows.append([btn("Добавить товар", "addprod", icon="add")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("box")} <b>Товары</b>\n\n<blockquote>Выберите категорию:</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("box")} <b>Товары</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("apcat_"))
async def cb_apcat(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    cid   = int(cb.data.split("_")[1])
    prods = await get_products(cid)
    rows  = []
    for p in prods:
        rows.append([
            btn(f"📦 {p['name']} — {fmt_price(p['price'])} (x{p['stock']})",
                f"vprod_{p['id']}"),
            btn("Ред.", f"editprod_{p['id']}", icon="edit"),
            btn("Уд.",  f"dprod_{p['id']}",   icon="delete"),
        ])
    rows.append([btn("Назад", "adm_products", icon="back")])
    try:
        await cb.message.edit_text(
            "<blockquote>📦 Товары категории:</blockquote>",
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer("📦 Товары:", parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("vprod_"))
async def cb_vprod(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    pid = int(cb.data.split("_")[1])
    p   = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    sizes = parse_sizes(p)
    text = (
        f'{ae("box")} <b>{p["name"]}</b>\n\n'
        f'{p["description"]}\n\n'
        f"━━━━━━━━━━━━━━━━━\n"
        f'{ae("money")} <b>Цена:</b> {fmt_price(p["price"])}\n'
        f'{ae("size")} <b>Размеры:</b> {", ".join(sizes) or "—"}\n'
        f'{ae("box")} <b>Остаток:</b> {p["stock"]} шт.\n'
        f'{ae("phone")} <b>Тел. продавца:</b> {p["seller_phone"] or "—"}\n'
        f'💬 <b>TG продавца:</b> {"@" + p["seller_username"] if p["seller_username"] else "—"}\n'
        f"━━━━━━━━━━━━━━━━━"
    )
    markup = kb(
        [btn("Редактировать", f"editprod_{pid}", icon="edit")],
        [btn("Назад", "adm_products", icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


EDIT_FIELD_LABELS = {
    "name":            ("📛 Название",     "Введите новое название:"),
    "description":     ("📝 Описание",     "Введите новое описание:"),
    "price":           ("💰 Цена",         "Введите новую цену в ₸:"),
    "stock":           ("📊 Остаток",      "Введите количество на складе:"),
    "sizes":           ("📐 Размеры",      "Введите размеры через запятую (или «нет»):"),
    "seller_phone":    ("📞 Телефон",      "Введите номер телефона продавца:"),
    "seller_username": ("💬 TG username",  "Введите @username продавца (или «нет»):"),
}


@router.callback_query(F.data.startswith("editprod_"))
async def cb_editprod(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    pid = int(cb.data.split("_")[1])
    p   = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    markup = kb(
        [btn("Название",   f"epf_{pid}_name",            icon="edit"),
         btn("Описание",   f"epf_{pid}_description",     icon="edit")],
        [btn("Цена",       f"epf_{pid}_price",            icon="money"),
         btn("Остаток",    f"epf_{pid}_stock",            icon="box")],
        [btn("Размеры",    f"epf_{pid}_sizes",            icon="size"),
         btn("Тел.",       f"epf_{pid}_seller_phone",     icon="phone")],
        [btn("TG продавца", f"epf_{pid}_seller_username", icon="chat")],
        [btn("Назад",       f"vprod_{pid}",               icon="back")],
    )
    try:
        await cb.message.edit_text(
            f'✏️ <b>Редактирование: {p["name"]}</b>\n\n'
            f'<blockquote>Выберите поле для изменения:</blockquote>',
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer("✏️ Редактирование", parse_mode="HTML",
                                reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("epf_"))
async def cb_epf(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    parts = cb.data.split("_", 2)
    pid   = int(parts[1])
    field = parts[2]
    label, prompt = EDIT_FIELD_LABELS.get(field, (field, f"Введите значение для {field}:"))
    await state.update_data(edit_pid=pid, edit_field=field)
    await state.set_state(AdminSt.edit_prod_value)
    try:
        await cb.message.edit_text(
            f'✏️ <b>{label}</b>\n\n<blockquote>{prompt}</blockquote>',
            parse_mode="HTML", reply_markup=kb_back(f"editprod_{pid}"),
        )
    except Exception:
        await cb.message.answer(f"✏️ {prompt}", reply_markup=kb_back(f"editprod_{pid}"))
    await cb.answer()


@router.message(AdminSt.edit_prod_value)
async def proc_edit_prod_value(msg: types.Message, state: FSMContext):
    d     = await state.get_data()
    pid   = d.get("edit_pid")
    field = d.get("edit_field")
    await state.clear()
    raw   = msg.text.strip()
    value = raw
    if field == "price":
        try:
            value = float(raw.replace(",", ".").replace(" ", ""))
        except ValueError:
            await msg.answer("❌ Введите число.", reply_markup=kb_admin_back())
            return
    elif field == "stock":
        try:
            value = int(raw)
        except ValueError:
            await msg.answer("❌ Введите целое число.", reply_markup=kb_admin_back())
            return
    elif field == "sizes":
        if raw.lower() in ("нет", "no", "-", "—"):
            value = "[]"
        else:
            value = json.dumps([s.strip().upper() for s in raw.split(",") if s.strip()],
                               ensure_ascii=False)
    elif field == "seller_username":
        value = "" if raw.lower() in ("нет", "no", "-", "—") else raw.lstrip("@")
    await update_product_field(pid, field, value)
    label = EDIT_FIELD_LABELS.get(field, (field,))[0]
    await msg.answer(
        f"✅ <b>{label} обновлено!</b>\n\n<code>{value}</code>",
        parse_mode="HTML", reply_markup=kb_admin_back(),
    )


@router.callback_query(F.data.startswith("dprod_"))
async def cb_dprod(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    pid = int(cb.data.split("_")[1])
    await del_product(pid)
    await cb.answer("✅ Товар удалён", show_alert=True)
    try:
        await cb.message.edit_text(
            "✅ Товар удалён",
            reply_markup=kb([btn("Назад", "adm_products", icon="back")]),
        )
    except Exception:
        pass


# ── Добавление товара (9 шагов) ───────────────────────
@router.callback_query(F.data == "addprod")
async def cb_addprod(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    all_cats = await get_all_categories()
    if not all_cats:
        await cb.answer("Сначала создайте категорию!", show_alert=True)
        return
    rows = []
    for c in all_cats:
        prefix = "  ↳ " if c.get("parent_id", 0) else ""
        rows.append([btn(f"{prefix}{c['name']}", f"npcat_{c['id']}")])
    rows.append([btn("Назад", "adm_products", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("box")} <b>Новый товар</b>\n\n'
            f'<blockquote>Шаг 1/9 — Выберите категорию:</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("box")} <b>Новый товар</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("npcat_"))
async def cb_npcat(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    cid = int(cb.data.split("_")[1])
    await state.update_data(cid=cid)
    await state.set_state(AdminSt.add_prod_name)
    try:
        await cb.message.edit_text(
            f'{ae("box")} <b>Шаг 2/9 — Название товара</b>\n\n'
            f'<blockquote>Введите название:</blockquote>',
            parse_mode="HTML", reply_markup=kb_back("addprod"),
        )
    except Exception:
        await cb.message.answer("📦 Введите название товара:")
    await cb.answer()


@router.message(AdminSt.add_prod_name)
async def proc_prod_name(msg: types.Message, state: FSMContext):
    name = msg.html_text if msg.entities else msg.text
    await state.update_data(name=name)
    await state.set_state(AdminSt.add_prod_desc)
    await msg.answer(
        f'{ae("box")} <b>Шаг 3/9 — Описание товара</b>\n\n'
        f'<blockquote>Введите описание:</blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_desc)
async def proc_prod_desc(msg: types.Message, state: FSMContext):
    desc = msg.html_text if msg.entities else msg.text
    await state.update_data(desc=desc)
    await state.set_state(AdminSt.add_prod_price)
    await msg.answer(
        f'{ae("box")} <b>Шаг 4/9 — Цена в тенге ₸</b>\n\n'
        f'<blockquote>Введите цену (например: 5000):</blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_price)
async def proc_prod_price(msg: types.Message, state: FSMContext):
    try:
        price = float(msg.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await msg.answer("❌ Введите число, например: <code>5000</code>", parse_mode="HTML")
        return
    await state.update_data(price=price)
    await state.set_state(AdminSt.add_prod_sizes)
    await msg.answer(
        f'{ae("box")} <b>Шаг 5/9 — Размеры</b>\n\n'
        f'<blockquote>Через запятую: S, M, L, XL\n'
        f'Нет размеров — напишите <b>нет</b></blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_sizes)
async def proc_prod_sizes(msg: types.Message, state: FSMContext):
    raw = msg.text.strip()
    sizes_list = [] if raw.lower() in ("нет", "no", "-", "—") else \
                 [s.strip().upper() for s in raw.split(",") if s.strip()]
    await state.update_data(sizes=sizes_list)
    await state.set_state(AdminSt.add_prod_stock)
    await msg.answer(
        f'{ae("box")} <b>Шаг 6/9 — Остаток на складе</b>\n\n'
        f'<blockquote>Введите количество (например: 10):</blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_stock)
async def proc_prod_stock(msg: types.Message, state: FSMContext):
    try:
        stock = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите целое число.")
        return
    await state.update_data(stock=stock)
    await state.set_state(AdminSt.add_prod_seller_ph)
    await msg.answer(
        f'{ae("box")} <b>Шаг 7/9 — Телефон продавца</b>\n\n'
        f'<blockquote>Пример: +7 701 234 56 78\nНапишите <b>нет</b> если нет.</blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_seller_ph)
async def proc_prod_seller_ph(msg: types.Message, state: FSMContext):
    phone = "" if msg.text.strip().lower() in ("нет", "no", "-") else msg.text.strip()
    await state.update_data(seller_phone=phone)
    await state.set_state(AdminSt.add_prod_seller_un)
    await msg.answer(
        f'{ae("box")} <b>Шаг 8/9 — Telegram продавца</b>\n\n'
        f'<blockquote>Введите @username или напишите <b>нет</b>:</blockquote>',
        parse_mode="HTML", reply_markup=kb_back("addprod"),
    )


@router.message(AdminSt.add_prod_seller_un)
async def proc_prod_seller_un(msg: types.Message, state: FSMContext):
    raw  = msg.text.strip()
    un   = "" if raw.lower() in ("нет", "no", "-", "—") else raw.lstrip("@")
    await state.update_data(seller_un=un)
    await state.set_state(AdminSt.add_prod_card)
    await msg.answer(
        f'{ae("box")} <b>Шаг 9/9 — Обложка товара</b>\n\n'
        f'<blockquote>Отправьте фото/видео или напишите <b>нет</b>.</blockquote>',
        parse_mode="HTML",
    )


@router.message(AdminSt.add_prod_card, F.photo | F.video)
async def proc_prod_card_media(msg: types.Message, state: FSMContext):
    if msg.photo:
        fid, mt = msg.photo[-1].file_id, "photo"
    else:
        fid, mt = msg.video.file_id, "video"
    await state.update_data(card_fid=fid, card_mt=mt)
    await _finish_add_product(msg, state)


@router.message(AdminSt.add_prod_card, F.text)
async def proc_prod_card_skip(msg: types.Message, state: FSMContext):
    if msg.text.strip().lower() in ("нет", "no", "-"):
        await state.update_data(card_fid="", card_mt="")
        await _finish_add_product(msg, state)
    else:
        await msg.answer("⚠️ Отправьте фото/видео или напишите «нет».")


async def _finish_add_product(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    pid = await add_product(
        d["cid"], d["name"], d["desc"], d["price"],
        d.get("sizes", []), d["stock"],
        d.get("seller_un", ""), d.get("seller_phone", ""),
        d.get("card_fid", ""), d.get("card_mt", ""),
    )
    await msg.answer(
        f'{ae("ok")} <b>Товар добавлен!</b>\n\n'
        f'{ae("box")} {d["name"]}\n'
        f'{ae("money")} {fmt_price(d["price"])}',
        parse_mode="HTML",
        reply_markup=kb_admin_back(),
    )


# ════════════════════════════════════════════════════
#  Заказы
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_orders")
async def cb_adm_orders(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    orders = await db_all(
        "SELECT o.*, p.name AS pname FROM orders o "
        "JOIN products p ON o.product_id=p.id "
        "ORDER BY o.created_at DESC LIMIT 20"
    )
    if not orders:
        await cb.answer("Заказов пока нет", show_alert=True)
        return
    rows = []
    for o in orders:
        uname = f"@{o['username']}" if o.get("username") else ""
        label = f"#{o['id']} {uname} {o['pname'][:10]} ({o['size']}) — {order_status_text(o['status'])}"
        rows.append([btn(label, f"orddetail_{o['id']}")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            "📋 <b>Заказы</b>\n<blockquote>Нажмите для просмотра:</blockquote>",
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer("📋 <b>Заказы</b>", parse_mode="HTML",
                                reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("orddetail_"))
async def cb_orddetail(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    oid   = int(cb.data.split("_")[1])
    order = await get_order(oid)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    product  = await get_product(order["product_id"])
    uname_s  = f"@{order['username']}" if order.get("username") else "—"
    promo_ln = ""
    if order.get("promo_code"):
        promo_ln = (
            f"🎟 <b>Промокод:</b> <code>{order['promo_code']}</code>\n"
            f"💰 <b>Скидка:</b> {fmt_price(order.get('discount', 0))}\n"
        )
    text = (
        f"📋 <b>Заказ #{oid}</b>\n\n━━━━━━━━━━━━━━━━━\n"
        f"{ae('user')} <b>Покупатель:</b> {uname_s}\n"
        f"👤 <b>Имя:</b> {order.get('first_name') or '—'}\n"
        f"🆔 <b>TG ID:</b> <code>{order['user_id']}</code>\n"
        f"{ae('box')} <b>Товар:</b> {product['name'] if product else '—'}\n"
        f"{ae('size')} <b>Размер:</b> {order['size']}\n"
        f"{ae('money')} <b>Сумма:</b> {fmt_price(order['price'])}\n"
        f"{promo_ln}"
        f"💳 <b>Оплата:</b> {order['method']}\n"
        f"{ae('phone')} <b>Телефон:</b> {order['phone'] or '—'}\n"
        f"{ae('pin')} <b>Адрес:</b> {order['address'] or '—'}\n"
        f"🔄 <b>Статус:</b> {order_status_text(order['status'])}\n"
        f"{ae('cal')} {order['created_at'][:16]}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    markup = kb(
        [btn("Изменить статус",    f"ordstatus_{oid}",             icon="refresh")],
        [btn("Написать покупателю", f"adm_msguser_{order['user_id']}", icon="chat")],
        [btn("Назад",               "adm_orders",                  icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("ordstatus_"))
async def cb_ordstatus(cb: types.CallbackQuery):
    if cb.from_user.id != MANAGER_ID and not admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    oid   = int(cb.data.split("_")[1])
    order = await get_order(oid)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    statuses = [
        ("🔄 В обработке", "processing"),
        ("✈️ Едет из Китая", "china"),
        ("📦 Прибыло",      "arrived"),
        ("🚚 Передано",     "delivered"),
        ("✅ Подтверждено", "confirmed"),
    ]
    rows = [[btn(label, f"setordst_{oid}_{st}")] for label, st in statuses]
    rows.append([btn("Произвольный статус", f"customst_{oid}", icon="edit")])
    rows.append([btn("Назад", f"orddetail_{oid}", icon="back")])
    uname_info = f"\n@{order['username']}" if order.get("username") else ""
    text = (
        f"📋 <b>Заказ #{oid}</b>{uname_info}\n"
        f"Статус: {order_status_text(order['status'])}\n\n"
        f"<blockquote>Выберите новый статус:</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("setordst_"))
async def cb_setordst(cb: types.CallbackQuery, bot: Bot):
    if cb.from_user.id != MANAGER_ID and not admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    parts  = cb.data.split("_", 2)
    oid    = int(parts[1])
    status = parts[2]
    order  = await get_order(oid)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    await set_order_status(oid, status, cb.from_user.id)
    product = await get_product(order["product_id"])
    pname   = product["name"] if product else "—"

    try:
        if status == "delivered":
            await bot.send_message(
                order["user_id"],
                f'{ae("truck")} <b>Ваш заказ #{oid} доставлен!</b>\n\n'
                f'{ae("bag")} {pname} ({order["size"]})\n\n'
                f'<blockquote>{ae("ok")} Пожалуйста, подтвердите получение:</blockquote>',
                parse_mode="HTML",
                reply_markup=kb([btn("Подтвердить получение",
                                     f"confirm_order_{oid}", icon="ok")]),
            )
        else:
            await bot.send_message(
                order["user_id"],
                f'{ae("bell")} <b>Статус заказа #{oid} обновлён</b>\n\n'
                f'{ae("bag")} {pname} ({order["size"]})\n'
                f'{ae("refresh")} <b>Новый статус:</b> {order_status_text(status)}',
                parse_mode="HTML",
            )
    except Exception:
        pass

    await cb.answer(f"✅ {order_status_text(status)}", show_alert=True)
    try:
        await cb.message.edit_text(
            cb.message.html_text + f"\n\n→ {order_status_text(status)}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("customst_"))
async def cb_customst(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != MANAGER_ID and not admin_guard(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    oid = int(cb.data.split("_")[1])
    await state.update_data(custom_oid=oid)
    await state.set_state(AdminSt.set_custom_status)
    try:
        await cb.message.edit_text(
            f"✏️ <b>Произвольный статус для заказа #{oid}</b>\n\n"
            f"<blockquote>Введите текст статуса (например: «Сортировочный центр»):</blockquote>",
            parse_mode="HTML",
            reply_markup=kb([btn("Назад", f"ordstatus_{oid}", icon="back")]),
        )
    except Exception:
        pass
    await cb.answer()


@router.message(AdminSt.set_custom_status)
async def proc_custom_status(msg: types.Message, state: FSMContext, bot: Bot):
    d      = await state.get_data()
    oid    = d.get("custom_oid")
    status = msg.text.strip()[:100]
    await state.clear()
    if not oid:
        await msg.answer("❌ Ошибка: заказ не найден.", reply_markup=kb_admin_back())
        return
    order   = await get_order(oid)
    product = await get_product(order["product_id"]) if order else None
    await set_order_status(oid, status)
    pname = product["name"] if product else "—"
    try:
        await bot.send_message(
            order["user_id"],
            f'{ae("truck")} <b>Статус заказа #{oid} обновлён</b>\n\n'
            f'{ae("box")} {pname} ({order["size"]})\n'
            f"🔄 <b>Новый статус:</b> {status}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await msg.answer(
        f"✅ <b>Статус заказа #{oid} обновлён:</b>\n<i>{status}</i>",
        parse_mode="HTML",
        reply_markup=kb_admin_back(),
    )


# ════════════════════════════════════════════════════
#  Пользователи
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_users")
async def cb_adm_users(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    users = await get_all_users(limit=20)
    rows  = []
    for u in users:
        ban_icon = "🚫" if u.get("is_banned") else "👤"
        uname    = f"@{u['username']}" if u.get("username") else str(u["user_id"])
        rows.append([btn(f"{ban_icon} {uname} — {u.get('first_name','?')[:15]}",
                         f"adm_user_{u['user_id']}")])
    rows.append([btn("Написать пользователю", "adm_msg_user", icon="chat")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("users")} <b>Пользователи</b>\n'
            f'<blockquote>Последние 20 зарегистрированных:</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("users")} <b>Пользователи</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("adm_user_"))
async def cb_adm_user(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    uid  = int(cb.data.split("_")[2])
    user = await get_user(uid)
    if not user:
        await cb.answer("Пользователь не найден", show_alert=True)
        return
    uname    = f"@{user['username']}" if user.get("username") else "—"
    ban_icon = "🚫 Заблокирован" if user.get("is_banned") else "✅ Активен"
    text = (
        f"{ae('user')} <b>Пользователь</b>\n\n━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"💬 <b>Username:</b> {uname}\n"
        f"📛 <b>Имя:</b> {user.get('first_name','—')}\n"
        f"📱 <b>Телефон:</b> {user.get('phone','—')}\n"
        f"📍 <b>Адрес:</b> {user.get('default_address','—')}\n"
        f"🛍 <b>Заказов:</b> {user.get('total_purchases',0)}\n"
        f"💰 <b>Потрачено:</b> {fmt_price(user.get('total_spent',0))}\n"
        f"🎁 <b>Бонусов:</b> {fmt_price(user.get('bonus_balance',0))}\n"
        f"📅 <b>Регистрация:</b> {user.get('registered_at','—')[:10]}\n"
        f"🔒 <b>Статус:</b> {ban_icon}\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    ban_btn = (btn("Разблокировать", f"adm_unban_{uid}", icon="unlock")
               if user.get("is_banned") else
               btn("Заблокировать",  f"adm_ban_{uid}",   icon="lock"))
    current_role = await get_user_role(uid)
    role_label   = ROLES.get(current_role, current_role or "—")
    markup = kb(
        [ban_btn],
        [btn(f"Роль: {role_label}", f"adm_role_edit_{uid}", icon="crown")],
        [btn("Написать пользователю", f"adm_msguser_{uid}", icon="chat")],
        [btn("Назад", "adm_users", icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("adm_ban_"))
async def cb_adm_ban(cb: types.CallbackQuery, bot: Bot):
    if not admin_guard(cb.from_user.id):
        return
    uid = int(cb.data.split("_")[2])
    await ban_user(uid)
    try:
        await bot.send_message(uid, "🚫 Вы заблокированы в этом боте.")
    except Exception:
        pass
    await cb.answer("🚫 Заблокирован", show_alert=True)
    await cb_adm_user(cb)


@router.callback_query(F.data.startswith("adm_unban_"))
async def cb_adm_unban(cb: types.CallbackQuery, bot: Bot):
    if not admin_guard(cb.from_user.id):
        return
    uid = int(cb.data.split("_")[2])
    await unban_user(uid)
    try:
        await bot.send_message(uid, "✅ Вы разблокированы.")
    except Exception:
        pass
    await cb.answer("✅ Разблокирован", show_alert=True)
    await cb_adm_user(cb)


@router.callback_query(F.data.startswith("adm_role_edit_"))
async def cb_adm_role_edit(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    uid  = int(cb.data.split("_")[3])
    rows = [[btn(label, f"adm_setrole_{uid}_{role}")] for role, label in ROLES.items()]
    rows.append([btn("Назад", f"adm_user_{uid}", icon="back")])
    try:
        await cb.message.edit_text(
            f"👑 <b>Выберите роль для пользователя</b>",
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("adm_setrole_"))
async def cb_adm_setrole(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    parts = cb.data.split("_")
    uid   = int(parts[2])
    role  = parts[3]
    await set_user_role(uid, role, cb.from_user.id)
    await cb.answer(f"✅ Роль обновлена: {ROLES.get(role, role)}", show_alert=True)
    await cb_adm_user(cb)


@router.callback_query(F.data == "adm_msg_user")
async def cb_adm_msg_user(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    await state.set_state(AdminSt.msg_user_id)
    try:
        await cb.message.edit_text(
            "💬 <b>Написать пользователю</b>\n\n"
            "<blockquote>Введите Telegram ID пользователя:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_back("adm_users"),
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("adm_msguser_"))
async def cb_adm_msguser(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    uid = int(cb.data.split("_")[2])
    await state.update_data(msg_target_uid=uid)
    await state.set_state(AdminSt.msg_user_text)
    try:
        await cb.message.edit_text(
            f"💬 <b>Сообщение пользователю</b> <code>{uid}</code>\n\n"
            f"<blockquote>Введите текст сообщения:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_back("adm_users"),
        )
    except Exception:
        pass
    await cb.answer()


@router.message(AdminSt.msg_user_id)
async def proc_msg_user_id(msg: types.Message, state: FSMContext):
    try:
        uid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите числовой ID.")
        return
    await state.update_data(msg_target_uid=uid)
    await state.set_state(AdminSt.msg_user_text)
    await msg.answer(f"💬 Введите текст сообщения для <code>{uid}</code>:",
                     parse_mode="HTML", reply_markup=kb_back("adm_users"))


@router.message(AdminSt.msg_user_text)
async def proc_msg_user_text(msg: types.Message, state: FSMContext, bot: Bot):
    d   = await state.get_data()
    uid = d.get("msg_target_uid")
    await state.clear()
    try:
        await bot.send_message(uid, msg.text, parse_mode="HTML")
        await msg.answer("✅ Сообщение отправлено.", reply_markup=kb_admin_back())
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}", reply_markup=kb_admin_back())


# ════════════════════════════════════════════════════
#  Промокоды
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_promos")
async def cb_adm_promos(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    promos = await get_all_promos()
    rows   = []
    for p in promos:
        rows.append([
            btn(f"🏷 {p['code']} — {p['promo_type']} ({p['used_count']} использ.)",
                f"viewpromo_{p['id']}"),
            btn("Удалить", f"delpromo_{p['id']}", icon="delete"),
        ])
    rows.append([btn("Новый промокод", "addpromo", icon="add")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("promo")} <b>Промокоды</b>\n'
            f'<blockquote>Активных: {len(promos)}</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("promo")} <b>Промокоды</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data == "addpromo")
async def cb_addpromo(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    await state.set_state(AdminSt.promo_code)
    try:
        await cb.message.edit_text(
            f'{ae("promo")} <b>Новый промокод</b>\n\n'
            f'<blockquote>Шаг 1/5 — Введите код промокода (например: SUMMER20):</blockquote>',
            parse_mode="HTML", reply_markup=kb_back("adm_promos"),
        )
    except Exception:
        await cb.message.answer("Введите код промокода:")
    await cb.answer()


@router.message(AdminSt.promo_code)
async def proc_promo_code(msg: types.Message, state: FSMContext):
    await state.update_data(promo_code=msg.text.strip().upper())
    await state.set_state(AdminSt.promo_type)
    rows = [[btn(label, f"promotype_{key}")] for key, label in PROMO_TYPES.items()]
    await msg.answer(
        f'{ae("promo")} <b>Шаг 2/5 — Тип промокода</b>',
        parse_mode="HTML", reply_markup=kb(*rows),
    )


@router.callback_query(F.data.startswith("promotype_"))
async def cb_promotype(cb: types.CallbackQuery, state: FSMContext):
    ptype = cb.data[len("promotype_"):]
    await state.update_data(promo_type=ptype)
    await state.set_state(AdminSt.promo_value)
    try:
        await cb.message.edit_text(
            f'{ae("promo")} <b>Шаг 3/5 — Значение</b>\n\n'
            f'<blockquote>Введите значение (для % — число, для ₸ — сумма):</blockquote>',
            parse_mode="HTML", reply_markup=kb_back("addpromo"),
        )
    except Exception:
        pass
    await cb.answer()


@router.message(AdminSt.promo_value)
async def proc_promo_value(msg: types.Message, state: FSMContext):
    try:
        val = float(msg.text.replace(",", "."))
    except ValueError:
        await msg.answer("❌ Введите число.")
        return
    await state.update_data(promo_value=val)
    await state.set_state(AdminSt.promo_description)
    await msg.answer(
        f'{ae("promo")} <b>Шаг 4/5 — Описание</b>\n\n'
        f'<blockquote>Введите описание промокода:</blockquote>',
        parse_mode="HTML",
    )


@router.message(AdminSt.promo_description)
async def proc_promo_description(msg: types.Message, state: FSMContext):
    await state.update_data(promo_desc=msg.text.strip())
    await state.set_state(AdminSt.promo_max_uses)
    await msg.answer(
        f'{ae("promo")} <b>Шаг 5/5 — Лимит использований</b>\n\n'
        f'<blockquote>Введите максимальное количество использований.\n'
        f'0 — без ограничений.</blockquote>',
        parse_mode="HTML",
    )


@router.message(AdminSt.promo_max_uses)
async def proc_promo_max_uses(msg: types.Message, state: FSMContext):
    try:
        max_uses = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите целое число.")
        return
    d = await state.get_data()
    await state.clear()
    pid = await create_promo(
        d["promo_code"], d["promo_type"], d["promo_value"],
        d.get("promo_desc", ""), max_uses,
    )
    await msg.answer(
        f'{ae("ok")} <b>Промокод создан!</b>\n\n'
        f'🏷 <code>{d["promo_code"]}</code>\n'
        f'Тип: {PROMO_TYPES.get(d["promo_type"], d["promo_type"])}\n'
        f'Значение: {d["promo_value"]}\n'
        f'Лимит: {max_uses if max_uses > 0 else "∞"}',
        parse_mode="HTML",
        reply_markup=kb_admin_back(),
    )


@router.callback_query(F.data.startswith("delpromo_"))
async def cb_delpromo(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    pid = int(cb.data.split("_")[1])
    await delete_promo(pid)
    await cb.answer("✅ Промокод деактивирован", show_alert=True)
    await cb_adm_promos(cb)


# ════════════════════════════════════════════════════
#  Партнёры (просмотр)
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_partners")
async def cb_adm_partners(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    partners = await db_all(
        "SELECT p.*, u.username, u.first_name FROM partners p "
        "LEFT JOIN users u ON p.user_id=u.user_id ORDER BY p.created_at DESC LIMIT 30"
    )
    if not partners:
        await cb.answer("Партнёров пока нет", show_alert=True)
        return
    rows = []
    for p in partners:
        uname = f"@{p['username']}" if p.get("username") else str(p["user_id"])
        rows.append([btn(
            f"🤝 {uname} — {p['ref_code']} ({p['total_invited']}👥)",
            f"adm_partner_{p['user_id']}"
        )])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("partner")} <b>Партнёры</b>\n<blockquote>Всего: {len(partners)}</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("partner")} <b>Партнёры</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


# ════════════════════════════════════════════════════
#  Дропы (админ)
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_drops")
async def cb_adm_drops(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    drops = await get_all_drops_admin()
    rows  = []
    for d in drops:
        status = "🟢" if d["is_active"] else "🔴"
        rows.append([
            btn(f"{status} {d['name']} — {d['start_at'][:10]}", f"viewdrop_{d['id']}"),
            btn("Удалить", f"deldrop_{d['id']}", icon="delete"),
        ])
    rows.append([btn("Добавить дроп", "adddrop", icon="fire")])
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("fire")} <b>Дропы</b>\n<blockquote>Всего: {len(drops)}</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("fire")} <b>Дропы</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data == "adddrop")
async def cb_adddrop(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    all_cats = await get_all_categories()
    rows     = [[btn(c["name"], f"dropcat_{c['id']}")] for c in all_cats]
    rows.append([btn("Назад", "adm_drops", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("fire")} <b>Новый дроп</b>\n\n<blockquote>Шаг 1 — Категория:</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("fire")} <b>Новый дроп</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("dropcat_"))
async def cb_dropcat(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    cid = int(cb.data.split("_")[1])
    await state.update_data(drop_cid=cid)
    await state.set_state(AdminSt.add_drop_name)
    try:
        await cb.message.edit_text(
            f'{ae("fire")} <b>Шаг 2 — Название дропа:</b>',
            parse_mode="HTML", reply_markup=kb_back("adddrop"),
        )
    except Exception:
        await cb.message.answer("Введите название дропа:")
    await cb.answer()


@router.message(AdminSt.add_drop_name)
async def proc_drop_name(msg: types.Message, state: FSMContext):
    await state.update_data(drop_name=msg.text.strip())
    await state.set_state(AdminSt.add_drop_desc)
    await msg.answer(f'{ae("fire")} <b>Шаг 3 — Описание дропа:</b>',
                     parse_mode="HTML", reply_markup=kb_back("adddrop"))


@router.message(AdminSt.add_drop_desc)
async def proc_drop_desc(msg: types.Message, state: FSMContext):
    await state.update_data(drop_desc=msg.text.strip())
    await state.set_state(AdminSt.add_drop_price)
    await msg.answer(f'{ae("fire")} <b>Шаг 4 — Цена в ₸:</b>', parse_mode="HTML")


@router.message(AdminSt.add_drop_price)
async def proc_drop_price(msg: types.Message, state: FSMContext):
    try:
        price = float(msg.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await msg.answer("❌ Введите число.")
        return
    await state.update_data(drop_price=price)
    await state.set_state(AdminSt.add_drop_sizes)
    await msg.answer(
        f'{ae("fire")} <b>Шаг 5 — Размеры</b> (через запятую или «нет»):',
        parse_mode="HTML",
    )


@router.message(AdminSt.add_drop_sizes)
async def proc_drop_sizes(msg: types.Message, state: FSMContext):
    raw   = msg.text.strip()
    sizes = [] if raw.lower() in ("нет", "no", "-") else \
            [s.strip().upper() for s in raw.split(",") if s.strip()]
    await state.update_data(drop_sizes=sizes)
    await state.set_state(AdminSt.add_drop_stock)
    await msg.answer(f'{ae("fire")} <b>Шаг 6 — Количество (остаток):</b>',
                     parse_mode="HTML")


@router.message(AdminSt.add_drop_stock)
async def proc_drop_stock(msg: types.Message, state: FSMContext):
    try:
        stock = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите целое число.")
        return
    await state.update_data(drop_stock=stock)
    await state.set_state(AdminSt.add_drop_start_at)
    await msg.answer(
        f'{ae("fire")} <b>Шаг 7 — Дата и время старта продаж</b>\n\n'
        f'<blockquote>Формат: ДД.ММ.ГГГГ ЧЧ:ММ\nПример: 25.12.2025 12:00</blockquote>',
        parse_mode="HTML",
    )


@router.message(AdminSt.add_drop_start_at)
async def proc_drop_start(msg: types.Message, state: FSMContext):
    try:
        dt       = datetime.strptime(msg.text.strip(), "%d.%m.%Y %H:%M")
        start_at = dt.isoformat()
    except ValueError:
        await msg.answer("❌ Неверный формат. Введите: ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    await state.update_data(drop_start_at=start_at)
    await state.set_state(AdminSt.add_drop_card)
    await msg.answer(
        f'{ae("fire")} <b>Шаг 8 — Фото/видео дропа</b>\n\n'
        f'<blockquote>Отправьте фото или напишите <b>нет</b>.</blockquote>',
        parse_mode="HTML",
    )


@router.message(AdminSt.add_drop_card, F.photo | F.video)
async def proc_drop_card_media(msg: types.Message, state: FSMContext):
    if msg.photo:
        fid, mt = msg.photo[-1].file_id, "photo"
    else:
        fid, mt = msg.video.file_id, "video"
    await state.update_data(drop_card_fid=fid, drop_card_mt=mt)
    await _finish_add_drop(msg, state)


@router.message(AdminSt.add_drop_card, F.text)
async def proc_drop_card_skip(msg: types.Message, state: FSMContext):
    if msg.text.strip().lower() in ("нет", "no", "-"):
        await state.update_data(drop_card_fid="", drop_card_mt="")
        await _finish_add_drop(msg, state)
    else:
        await msg.answer("⚠️ Отправьте фото/видео или напишите «нет».")


async def _finish_add_drop(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    did = await add_drop(
        d.get("drop_cid", 0), d["drop_name"], d["drop_desc"], d["drop_price"],
        d.get("drop_sizes", []), d["drop_stock"], d["drop_start_at"],
        d.get("drop_card_fid", ""), d.get("drop_card_mt", ""),
    )
    start_fmt = d["drop_start_at"][:16].replace("T", " ")
    await msg.answer(
        f'{ae("ok")} <b>Дроп добавлен!</b>\n\n'
        f'{ae("fire")} <b>{d["drop_name"]}</b>\n'
        f'{ae("money")} {fmt_price(d["drop_price"])}\n'
        f'⏰ Старт: {start_fmt}',
        parse_mode="HTML",
        reply_markup=kb_admin_back(),
    )


@router.callback_query(F.data.startswith("deldrop_"))
async def cb_deldrop(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    did = int(cb.data.split("_")[1])
    await del_drop(did)
    await cb.answer("✅ Дроп удалён", show_alert=True)
    await cb_adm_drops(cb)


# ════════════════════════════════════════════════════
#  Настройки магазина
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_settings")
async def cb_adm_settings(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    markup = kb(
        [btn("Описание магазина", "edit_shop_info", icon="edit")],
        [btn("Назад", "adm_panel", icon="back")],
    )
    try:
        await cb.message.edit_text(
            f'{ae("settings")} <b>Настройки магазина</b>',
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer(f'{ae("settings")} <b>Настройки</b>',
                                parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "edit_shop_info")
async def cb_edit_shop(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    await state.set_state(AdminSt.edit_shop_info)
    try:
        await cb.message.edit_text(
            "📝 <b>Описание магазина</b>\n\n<blockquote>Введите новое описание:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb([btn("Назад", "adm_settings", icon="back")]),
        )
    except Exception:
        await cb.message.answer("📝 Введите описание магазина:")
    await cb.answer()


@router.message(AdminSt.edit_shop_info)
async def proc_shop_info(msg: types.Message, state: FSMContext):
    await set_setting("shop_info", msg.text)
    await state.clear()
    await msg.answer("✅ Описание обновлено!", reply_markup=kb_admin_back())


# ════════════════════════════════════════════════════
#  Редактирование сообщений бота
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_botmsgs")
async def cb_adm_botmsgs(cb: types.CallbackQuery):
    if not admin_guard(cb.from_user.id):
        return
    rows = [[btn(label, f"edit_botmsg_{key}", icon="edit")]
            for key, label in BOT_MSG_KEYS_LABELS.items()]
    rows.append([btn("Назад", "adm_panel", icon="back")])
    try:
        await cb.message.edit_text(
            f'{ae("chat")} <b>Редактирование сообщений бота</b>\n\n'
            f'<blockquote>Выберите сообщение для редактирования:</blockquote>',
            parse_mode="HTML", reply_markup=kb(*rows),
        )
    except Exception:
        await cb.message.answer(f'{ae("chat")} <b>Сообщения бота</b>',
                                parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("edit_botmsg_"))
async def cb_edit_botmsg(cb: types.CallbackQuery, state: FSMContext):
    if not admin_guard(cb.from_user.id):
        return
    key     = cb.data[len("edit_botmsg_"):]
    label   = BOT_MSG_KEYS_LABELS.get(key, key)
    current = await get_bot_msg(key)
    await state.update_data(botmsg_key=key)
    await state.set_state(AdminSt.bot_msg_text)
    try:
        await cb.message.edit_text(
            f'✏️ <b>{label}</b>\n\n'
            f'<blockquote>Текущее:\n<i>{current[:300]}</i></blockquote>\n\n'
            f'Введите новый текст (HTML разметка поддерживается).\n'
            f'Напишите <b>сброс</b> для возврата к дефолтному.',
            parse_mode="HTML",
            reply_markup=kb_back("adm_botmsgs"),
        )
    except Exception:
        await cb.message.answer(f'✏️ <b>{label}</b>\n\nВведите новый текст:',
                                parse_mode="HTML")
    await cb.answer()


@router.message(AdminSt.bot_msg_text)
async def proc_bot_msg_text(msg: types.Message, state: FSMContext):
    d   = await state.get_data()
    key = d.get("botmsg_key", "")
    await state.clear()
    raw = msg.text.strip()
    if raw.lower() in ("сброс", "reset"):
        await db_run("DELETE FROM bot_messages WHERE key=$1", (key,))
        await msg.answer("✅ Сообщение сброшено к дефолтному.",
                         reply_markup=kb_admin_back())
        return
    await set_bot_msg(key, raw)
    label = BOT_MSG_KEYS_LABELS.get(key, key)
    await msg.answer(f"✅ <b>{label}</b> обновлено!", parse_mode="HTML",
                     reply_markup=kb_admin_back())


# ════════════════════════════════════════════════════
#  Лог / Отчёт
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "adm_log")
async def cb_adm_log(cb: types.CallbackQuery, bot: Bot):
    if not admin_guard(cb.from_user.id):
        return
    await cb.answer("📊 Генерирую отчёт…")
    since = (datetime.now() - timedelta(hours=24)).isoformat()

    purchases = await db_all(
        "SELECT pu.*, p.name AS pname, u.username FROM purchases pu "
        "LEFT JOIN products p ON p.id=pu.product_id "
        "LEFT JOIN users u ON u.user_id=pu.user_id "
        "WHERE pu.purchased_at >= $1 ORDER BY pu.purchased_at DESC", (since,)
    )
    orders = await db_all(
        "SELECT o.*, p.name AS pname FROM orders o "
        "LEFT JOIN products p ON p.id=o.product_id "
        "WHERE o.created_at >= $1 ORDER BY o.created_at DESC", (since,)
    )
    new_users  = await db_all("SELECT * FROM users WHERE registered_at >= $1", (since,))
    complaints = await db_all(
        "SELECT c.*, u.username, u.first_name FROM complaints c "
        "LEFT JOIN users u ON u.user_id=c.user_id WHERE c.created_at >= $1", (since,)
    )
    events     = await db_all("SELECT * FROM event_log WHERE created_at >= $1 LIMIT 100", (since,))
    total_rev  = sum(p["price"] for p in purchases)

    html = f"""<!DOCTYPE html><html lang="ru"><head>
<meta charset="UTF-8"><title>ShopBot Log</title>
<style>
  :root {{--bg:#0f0f1a;--card:#1a1a2e;--accent:#7c3aed;--accent2:#06b6d4;
          --green:#10b981;--red:#ef4444;--yellow:#f59e0b;--text:#e2e8f0;
          --muted:#64748b;--border:#2d2d44;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:var(--bg);color:var(--text);padding:20px}}
  .header{{background:linear-gradient(135deg,var(--accent),var(--accent2));
           border-radius:16px;padding:24px 32px;margin-bottom:24px}}
  .header h1{{font-size:1.8rem;font-weight:700}}
  .stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
               gap:16px;margin-bottom:24px}}
  .stat{{background:var(--card);border:1px solid var(--border);border-radius:12px;
         padding:20px;text-align:center}}
  .stat .val{{font-size:2rem;font-weight:700;color:var(--accent2)}}
  .stat .lbl{{font-size:.8rem;color:var(--muted);margin-top:4px}}
  .section{{background:var(--card);border:1px solid var(--border);
            border-radius:16px;margin-bottom:20px;overflow:hidden}}
  .section-header{{padding:16px 24px;background:linear-gradient(90deg,rgba(124,58,237,.2),transparent);
                   border-bottom:1px solid var(--border);font-weight:600}}
  table{{width:100%;border-collapse:collapse}}
  th{{padding:12px 16px;text-align:left;font-size:.75rem;text-transform:uppercase;
      color:var(--muted);background:rgba(255,255,255,.03);border-bottom:1px solid var(--border)}}
  td{{padding:12px 16px;font-size:.85rem;border-bottom:1px solid rgba(45,45,68,.5)}}
  .badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:600}}
  .bg{{background:rgba(16,185,129,.2);color:var(--green)}}
  .br{{background:rgba(239,68,68,.2);color:var(--red)}}
  .by{{background:rgba(245,158,11,.2);color:var(--yellow)}}
  .bb{{background:rgba(6,182,212,.2);color:var(--accent2)}}
  .empty{{padding:32px;text-align:center;color:var(--muted)}}
</style></head><body>
<div class="header">
  <h1>📊 ShopBot — Лог за 24 часа</h1>
  <p>Сгенерировано: {fmt_dt()} | {SHOP_NAME}</p>
</div>
<div class="stats-grid">
  <div class="stat"><div class="val">{len(purchases)}</div><div class="lbl">Покупок</div></div>
  <div class="stat"><div class="val">{fmt_price(total_rev)}</div><div class="lbl">Выручка</div></div>
  <div class="stat"><div class="val">{len(new_users)}</div><div class="lbl">Новых юзеров</div></div>
  <div class="stat"><div class="val">{len(orders)}</div><div class="lbl">Заказов</div></div>
  <div class="stat"><div class="val">{len(complaints)}</div><div class="lbl">Жалоб</div></div>
  <div class="stat"><div class="val">{len(events)}</div><div class="lbl">Событий</div></div>
</div>"""

    # Покупки
    html += '<div class="section"><div class="section-header">💰 Покупки</div>'
    if purchases:
        html += '<table><tr><th>#</th><th>Покупатель</th><th>Товар</th><th>Сумма</th><th>Метод</th><th>Время</th></tr>'
        for p in purchases:
            un = f"@{p['username']}" if p.get("username") else str(p["user_id"])
            bc = "bb" if p["method"] == "crypto" else "by"
            html += f"<tr><td>{p['id']}</td><td>{un}</td><td>{p['pname']}</td>"
            html += f"<td style='color:#10b981'>{fmt_price(p['price'])}</td>"
            html += f"<td><span class='badge {bc}'>{p['method'].upper()}</span></td>"
            html += f"<td>{p['purchased_at'][:16]}</td></tr>"
        html += "</table>"
    else:
        html += '<div class="empty">Покупок за 24 часа не было</div>'
    html += "</div>"

    # Новые пользователи
    html += '<div class="section"><div class="section-header">👥 Новые пользователи</div>'
    if new_users:
        html += '<table><tr><th>ID</th><th>Username</th><th>Имя</th><th>Регистрация</th></tr>'
        for u in new_users:
            html += f"<tr><td><code>{u['user_id']}</code></td>"
            html += f"<td>{'@'+u['username'] if u.get('username') else '—'}</td>"
            html += f"<td>{u.get('first_name','—')}</td><td>{u['registered_at'][:16]}</td></tr>"
        html += "</table>"
    else:
        html += '<div class="empty">Новых пользователей нет</div>'
    html += "</div></body></html>"

    buf = io.BytesIO(html.encode("utf-8"))
    fname = f"shopbot_log_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    await bot.send_document(
        cb.from_user.id,
        types.BufferedInputFile(buf.getvalue(), filename=fname),
        caption=f"📊 <b>Лог за 24 часа</b>\n{fmt_dt()}",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════
#  Сброс FSM при навигации
# ════════════════════════════════════════════════════
@router.callback_query(F.data.in_(NAV_CALLBACKS))
async def nav_clear_state(cb: types.CallbackQuery, state: FSMContext):
    if await state.get_state():
        await state.clear()
