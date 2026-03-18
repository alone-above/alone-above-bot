"""handlers/ads.py — Размещение рекламы"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ae, ADMIN_IDS, AD_PRICE_KZT
from db import create_ad_request, get_ad_request, set_ad_status
from keyboards import kb_back, btn, kb
from utils import fmt_price

router = Router()


class AdSt(StatesGroup):
    description = State()


AD_WARNING_TEXT = (
    "⚠️ <b>ВАЖНО! ОЗНАКОМЬТЕСЬ ДО ОПЛАТЫ</b>\n\n"
    "Уважаемые рекламодатели! Прежде чем оплатить заказ, "
    "внимательно прочитайте список.\n\n"
    "<b>МЫ НЕ РЕКЛАМИРУЕМ следующие тематики НИ ПРИ КАКИХ УСЛОВИЯХ:</b>\n\n"
    "<b>1. МОШЕННИЧЕСТВО И ФИНАНСОВЫЕ ПИРАМИДЫ</b>\n"
    "❌ Финансовые пирамиды, хайпы, сомнительные инвестиции.\n"
    "❌ Заработок в интернете «без вложений».\n"
    "❌ Продажа баз данных, слитой информации, взломов.\n\n"
    "<b>2. СПАМ И НАКРУТКИ</b>\n"
    "❌ Программы для рассылок. ❌ Накрутка подписчиков.\n\n"
    "<b>3. АЗАРТНЫЕ ИГРЫ</b>\n"
    "❌ Онлайн-казино. ❌ Букмекерские конторы без лицензии.\n\n"
    "<b>4. ВЗРОСЛЫЙ КОНТЕНТ (18+)</b>\n"
    "❌ Порно, эротика, интим-услуги.\n\n"
    "<b>5–7. ТОВАРЫ БЕЗ ДОКАЗАТЕЛЬСТВ / ПОЛИТИКА / КОНКУРЕНТЫ</b>\n"
    "❌ «Чудо-лекарства», политическая агитация, прямые конкуренты.\n\n"
    "⚠️ Если ваш товар в этом списке — <b>НЕ ОПЛАЧИВАЙТЕ</b>."
)


@router.callback_query(F.data == "ad_warning")
async def cb_ad_warning(cb: types.CallbackQuery):
    markup = kb(
        [btn("Ознакомлен, продолжить", "ad_continue", icon="ok")],
        [btn("Назад",                   "shop",         icon="back")],
    )
    try:
        await cb.message.edit_text(AD_WARNING_TEXT, parse_mode="HTML",
                                   reply_markup=markup)
    except Exception:
        await cb.message.answer(AD_WARNING_TEXT, parse_mode="HTML",
                                reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "ad_continue")
async def cb_ad_continue(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdSt.description)
    text = (
        f"📢 <b>Оформление рекламы</b>\n\n"
        f"<blockquote>Стоимость размещения: <b>{fmt_price(AD_PRICE_KZT)}</b>\n\n"
        f"Опишите вашу рекламу:\n"
        f"• Что рекламируете\n"
        f"• Ссылка / контакт\n"
        f"• Пожелания по формату</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_back("ad_warning"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML",
                                reply_markup=kb_back("ad_warning"))
    await cb.answer()


@router.message(AdSt.description)
async def proc_ad_desc(msg: types.Message, state: FSMContext):
    await state.clear()
    aid = await create_ad_request(msg.from_user.id, msg.text, "kaspi")
    uname = f"@{msg.from_user.username}" if msg.from_user.username else str(msg.from_user.id)

    notif = (
        f"📢 <b>Новая заявка на рекламу #{aid}</b>\n\n"
        f"👤 {uname} ({msg.from_user.first_name})\n"
        f"🆔 <code>{msg.from_user.id}</code>\n\n"
        f"📝 {msg.text[:500]}\n\n"
        f"💰 Сумма: {fmt_price(AD_PRICE_KZT)}"
    )
    mgr_markup = kb(
        [btn("✅ Принять",  f"ad_accept_{aid}", icon="ok")],
        [btn("❌ Отклонить", f"ad_reject_{aid}", icon="no")],
    )
    for aid_id in ADMIN_IDS:
        try:
            await msg.bot.send_message(aid_id, notif, parse_mode="HTML",
                                       reply_markup=mgr_markup)
        except Exception:
            pass

    from keyboards import kb_main
    await msg.answer(
        f"{ae('ok')} <b>Заявка #{aid} отправлена!</b>\n\n"
        f"<blockquote>Менеджер свяжется с вами для уточнения деталей "
        f"и оплаты в течение 24 часов.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


# ── Обработка решения администратора ─────────────────
@router.callback_query(F.data.startswith("ad_accept_"))
async def cb_ad_accept(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    aid = int(cb.data.split("_")[2])
    req = await get_ad_request(aid)
    if not req:
        await cb.answer("Заявка не найдена", show_alert=True)
        return
    await set_ad_status(aid, "accepted")
    try:
        await cb.bot.send_message(
            req["user_id"],
            f"✅ <b>Ваша рекламная заявка #{aid} принята!</b>\n\n"
            f"<blockquote>Менеджер свяжется с вами для оплаты и размещения.</blockquote>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer("✅ Принято")
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n✅ <b>ПРИНЯТО</b>", parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("ad_reject_"))
async def cb_ad_reject(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    aid = int(cb.data.split("_")[2])
    req = await get_ad_request(aid)
    if not req:
        await cb.answer("Заявка не найдена", show_alert=True)
        return
    await set_ad_status(aid, "rejected")
    try:
        await cb.bot.send_message(
            req["user_id"],
            f"❌ <b>Рекламная заявка #{aid} отклонена.</b>\n\n"
            f"<blockquote>К сожалению, мы не можем разместить вашу рекламу. "
            f"Если есть вопросы — обратитесь в поддержку.</blockquote>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer("❌ Отклонено")
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n❌ <b>ОТКЛОНЕНО</b>", parse_mode="HTML"
        )
    except Exception:
        pass
