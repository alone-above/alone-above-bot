"""handlers/support.py — Поддержка и жалобы"""
from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import SUPPORT_USERNAME, ae
from db import create_complaint, is_banned
from keyboards import kb_back, kb_support, btn, kb

router = Router()


class ComplaintSt(StatesGroup):
    order_id    = State()
    description = State()
    file_attach = State()


# ── Главная страница поддержки ─────────────────────────
async def show_support(bot: Bot, chat_id: int, edit_msg: types.Message | None = None):
    from db import get_media, db_run, _cache_invalidate
    text = (
        f"{ae('support')} <b>Поддержка</b>\n\n"
        f"<blockquote>По любым вопросам пишите нашему менеджеру "
        f"или в службу поддержки.</blockquote>"
    )
    markup = kb_support(SUPPORT_USERNAME)
    m = await get_media("support_menu")
    if m:
        mt = m["media_type"]
        if edit_msg:
            try:
                await edit_msg.delete()
            except Exception:
                pass
        try:
            if mt == "photo":
                await bot.send_photo(chat_id, m["file_id"], caption=text,
                                     parse_mode="HTML", reply_markup=markup)
                return
            elif mt == "video":
                await bot.send_video(chat_id, m["file_id"], caption=text,
                                     parse_mode="HTML", reply_markup=markup)
                return
            elif mt == "animation":
                await bot.send_animation(chat_id, m["file_id"], caption=text,
                                         parse_mode="HTML", reply_markup=markup)
                return
        except Exception:
            await db_run("DELETE FROM media_settings WHERE key='support_menu'")
            _cache_invalidate("media:support_menu")
    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            pass
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "support")
async def cb_support(cb: types.CallbackQuery, bot: Bot):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫 Вы заблокированы", show_alert=True)
        return
    await show_support(bot, cb.from_user.id, edit_msg=cb.message)
    await cb.answer()


@router.callback_query(F.data == "support_back")
async def cb_support_back(cb: types.CallbackQuery, bot: Bot):
    await show_support(bot, cb.from_user.id, edit_msg=cb.message)
    await cb.answer()


@router.callback_query(F.data == "support_contacts")
async def cb_support_contacts(cb: types.CallbackQuery):
    text = (
        f"📞 <b>Контакты</b>\n\n<blockquote>"
        f"📱 <b>Номер:</b> <a href='tel:+77078115621'>+7 707 811 5621</a>\n"
        f"🌍 <b>Страна:</b> Казахстан\n\n"
        f"🛍 <b>Telegram Магазина:</b> @aloneaboveshop\n"
        f"👤 <b>Telegram Владельца:</b> @AloneAbove\n"
        f"🤝 <b>Telegram Менеджера:</b> @AloneAboveManager\n"
        f"❓ <b>Telegram Поддержки:</b> @AloneAboveSupport\n\n"
        f"👑 <b>Владелец:</b> Кахраман Айбек\n"
        f"📧 <b>Email:</b> Alone.Above.0000@gmail.com\n"
        f"🌐 <b>Сайт:</b> <a href='https://t.me/alone_above_bot/shop'>"
        f"t.me/alone_above_bot/shop</a>"
        f"</blockquote>"
    )
    markup = kb(
        [btn("Написать менеджеру",
             url="https://t.me/AloneAboveManager", icon="chat")],
        [btn("Написать в поддержку",
             url="https://t.me/AloneAboveSupport", icon="chat")],
        [btn("Назад", "support_back", icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup,
                                   disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup,
                                disable_web_page_preview=True)
    await cb.answer()


# ── Жалобы ────────────────────────────────────────────
@router.callback_query(F.data == "complaint_start")
async def cb_complaint_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(ComplaintSt.order_id)
    text = (
        "⚠️ <b>Жалоба на товар</b>\n\n"
        "<blockquote>Шаг 1/2 — Укажите номер вашего заказа:\n"
        "<i>Например: 42</i>\n\n"
        "Если не помните номер — напишите <b>0</b></blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_back("support_back"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML",
                                reply_markup=kb_back("support_back"))
    await cb.answer()


@router.callback_query(F.data.startswith("complaint_order_"))
async def cb_complaint_from_order(cb: types.CallbackQuery, state: FSMContext):
    oid = int(cb.data.split("_")[2])
    await state.update_data(complaint_oid=oid)
    await state.set_state(ComplaintSt.description)
    text = (
        "⚠️ <b>Жалоба на товар</b>\n\n"
        "<blockquote>Опишите проблему подробно:\n\n"
        "• Что именно не так?\n"
        "• Когда заметили проблему?\n\n"
        "Ваше сообщение поможет нам решить ситуацию быстрее!</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_back(f"myorder_{oid}"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML",
                                reply_markup=kb_back(f"myorder_{oid}"))
    await cb.answer()


@router.message(ComplaintSt.order_id)
async def proc_complaint_oid(msg: types.Message, state: FSMContext):
    try:
        oid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите номер заказа (число) или 0.")
        return
    await state.update_data(complaint_oid=oid)
    await state.set_state(ComplaintSt.description)
    await msg.answer(
        "⚠️ <b>Шаг 2/2 — Описание проблемы</b>\n\n"
        "<blockquote>Опишите проблему подробно. "
        "При желании можете прикрепить фото.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_back("support_back"),
    )


@router.message(ComplaintSt.description)
async def proc_complaint_desc(msg: types.Message, state: FSMContext, bot: Bot):
    from config import ADMIN_IDS, MANAGER_ID
    d   = await state.get_data()
    oid = d.get("complaint_oid", 0)
    await state.clear()
    cid = await create_complaint(msg.from_user.id, oid, msg.text or "")
    uname = f"@{msg.from_user.username}" if msg.from_user.username else str(msg.from_user.id)
    notif = (
        f"⚠️ <b>Новая жалоба #{cid}</b>\n\n"
        f"👤 {uname} ({msg.from_user.first_name})\n"
        f"📦 Заказ: #{oid}\n"
        f"📝 {msg.text[:400]}"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, notif, parse_mode="HTML")
        except Exception:
            pass
    from keyboards import kb_main
    await msg.answer(
        f"{ae('ok')} <b>Жалоба #{cid} отправлена!</b>\n\n"
        f"<blockquote>Мы рассмотрим её в ближайшее время.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
