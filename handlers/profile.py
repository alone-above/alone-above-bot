"""handlers/profile.py — Профиль, телефон, адрес"""
from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import ROLES, ae
from db import (
    ensure_user, get_user, update_user_phone, update_user_address,
    get_user_role, cart_count, wish_count, is_banned,
)
from keyboards import kb_main, kb_back, kb_profile, btn, kb
from utils import fmt_price

router = Router()


class ProfileSt(StatesGroup):
    phone   = State()
    address = State()


def _profile_text(tg_user: types.User, user: dict, role: str = "buyer") -> str:
    phone      = user["phone"] if user["phone"] else "— не указан"
    address    = user["default_address"] if user["default_address"] else "— не указан"
    uname      = f"@{tg_user.username}" if tg_user.username else "— не указан"
    role_label = ROLES.get(role, role)
    return (
        f"{ae('user')} <b>Профиль</b>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ID:</b> <code>{tg_user.id}</code>\n"
        f"{ae('sparkle')} <b>Имя:</b> {tg_user.first_name or '—'}\n"
        f"{ae('chat')} <b>Username:</b> {uname}\n"
        f"{ae('crown')} <b>Роль:</b> {role_label}\n\n"
        f"{ae('phone')} <b>Телефон:</b> <code>{phone}</code>\n"
        f"{ae('pin')} <b>Адрес доставки:</b>\n  <i>{address}</i>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('cart')} <b>Заказов:</b> {user['total_purchases']}\n"
        f"{ae('cash')} <b>Потрачено:</b> {fmt_price(user['total_spent'])}\n"
        f"{ae('coin')} <b>Бонусный баланс:</b> {fmt_price(user['bonus_balance'])}\n"
        f"{ae('cal')} <b>Регистрация:</b> {user['registered_at'][:10]}\n"
        f"━━━━━━━━━━━━━━━━━"
    )


async def _send_profile(bot: Bot, tg_user: types.User, user: dict,
                        send_fn=None, edit_msg=None):
    if user is None:
        if send_fn:
            await send_fn("⏳ Профиль создаётся, попробуйте снова.", parse_mode="HTML")
        return
    role     = await get_user_role(tg_user.id)
    cnt_cart = await cart_count(tg_user.id)
    cnt_wish = await wish_count(tg_user.id)
    text     = _profile_text(tg_user, user, role)
    markup   = kb_profile(cnt_cart, cnt_wish)
    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            pass
    if send_fn:
        await send_fn(text, parse_mode="HTML", reply_markup=markup)
    else:
        await bot.send_message(tg_user.id, text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "profile_view")
async def cb_profile_view(cb: types.CallbackQuery, bot: Bot):
    await cb.answer()  # отвечаем как можно раньше, чтобы избежать "query is too old"
    await ensure_user(cb.from_user)
    user = await get_user(cb.from_user.id)
    await _send_profile(bot, cb.from_user, user, edit_msg=cb.message)


# ── Телефон ───────────────────────────────────────────
@router.callback_query(F.data == "profile_phone")
async def cb_profile_phone(cb: types.CallbackQuery):
    markup = kb(
        [btn("Поделиться через Telegram", "phone_via_tg", icon="mobile")],
        [btn("Ввести вручную",            "phone_manual",  icon="edit")],
        [btn("Назад",                     "profile_view",  icon="back")],
    )
    try:
        await cb.message.edit_text(
            "📞 <b>Укажите номер телефона</b>\n\n"
            "<blockquote>Выберите удобный способ:</blockquote>",
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer("📞 <b>Укажите номер телефона</b>",
                                parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "phone_via_tg")
async def cb_phone_via_tg(cb: types.CallbackQuery, bot: Bot):
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await bot.send_message(cb.from_user.id,
                           "📲 Нажмите кнопку ниже, чтобы поделиться номером:",
                           reply_markup=reply_kb)
    await cb.answer()


@router.message(F.contact)
async def handle_contact(msg: types.Message):
    if msg.contact.user_id != msg.from_user.id:
        await msg.answer("❌ Это чужой контакт.", reply_markup=kb_main())
        return
    phone = msg.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await update_user_phone(msg.from_user.id, phone)
    await msg.answer(
        f"✅ <b>Телефон сохранён:</b> <code>{phone}</code>\n\n"
        "Теперь вы можете делать заказы.",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


@router.callback_query(F.data == "phone_manual")
async def cb_phone_manual(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProfileSt.phone)
    try:
        await cb.message.edit_text(
            "📞 <b>Введите номер телефона вручную</b>\n"
            "<i>Пример: +7 701 234 56 78</i>",
            parse_mode="HTML",
            reply_markup=kb_back("profile_view"),
        )
    except Exception:
        await cb.message.answer("📞 <b>Введите номер телефона вручную</b>",
                                parse_mode="HTML", reply_markup=kb_back("profile_view"))
    await cb.answer()


@router.message(ProfileSt.phone)
async def proc_profile_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    await update_user_phone(msg.from_user.id, phone)
    await state.clear()
    await msg.answer(f"✅ <b>Телефон сохранён:</b> <code>{phone}</code>",
                     parse_mode="HTML", reply_markup=kb_main())


# ── Адрес ─────────────────────────────────────────────
@router.callback_query(F.data == "profile_address")
async def cb_profile_address(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProfileSt.address)
    try:
        await cb.message.edit_text(
            "📍 <b>Введите адрес доставки по умолчанию</b>\n"
            "<i>Пример: мкр Нурсат, ул. Байтурсынова 12, кв. 5</i>",
            parse_mode="HTML",
            reply_markup=kb_back("profile_view"),
        )
    except Exception:
        await cb.message.answer("📍 <b>Введите адрес доставки</b>",
                                parse_mode="HTML", reply_markup=kb_back("profile_view"))
    await cb.answer()


@router.message(ProfileSt.address)
async def proc_profile_address(msg: types.Message, state: FSMContext):
    address = msg.text.strip()
    await update_user_address(msg.from_user.id, address)
    await state.clear()
    await msg.answer(f"✅ <b>Адрес сохранён:</b>\n<i>{address}</i>",
                     parse_mode="HTML", reply_markup=kb_main())


# ── О магазине ────────────────────────────────────────
@router.callback_query(F.data == "about")
async def cb_about(cb: types.CallbackQuery, bot: Bot):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    from db import get_setting
    info   = await get_setting("shop_info", "Информация о магазине пока не заполнена.")
    text   = f"{ae('store')} <b>О магазине</b>\n\n<blockquote>{info}</blockquote>"
    markup = kb(
        [btn("Партнёрство", "partnership", icon="link")],
        [btn("Назад",       "main",        icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await bot.send_message(cb.from_user.id, text, parse_mode="HTML",
                               reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "about_back")
async def cb_about_back(cb: types.CallbackQuery):
    from db import get_setting
    info   = await get_setting("shop_info", "Информация о магазине пока не заполнена.")
    text   = f"{ae('store')} <b>О магазине</b>\n\n<blockquote>{info}</blockquote>"
    markup = kb(
        [btn("Партнёрство", "partnership", icon="link")],
        [btn("Назад",       "main",        icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "partnership")
async def cb_partnership(cb: types.CallbackQuery):
    from config import SUPPORT_USERNAME
    text = (
        f"{ae('store')} <b>Партнёрство с нами</b>\n\n<blockquote>"
        f"Мы открыты для взаимовыгодного сотрудничества!\n\n"
        f"🤝 <b>Что мы предлагаем:</b>\n"
        f"• Размещение вашего товара в нашем каталоге\n"
        f"• Рекламные интеграции в боте\n"
        f"• Совместные акции и распродажи\n"
        f"• Кросс-промо между магазинами\n\n"
        f"📈 <b>Почему мы?</b>\n"
        f"• Активная аудитория покупателей Шымкента\n"
        f"• Прозрачные условия сотрудничества\n"
        f"• Быстрая обратная связь\n\n"
        f"Если интересует сотрудничество — напишите нашему менеджеру!</blockquote>"
    )
    uname  = SUPPORT_USERNAME.lstrip("@")
    markup = kb(
        [btn("Связаться",        url=f"https://t.me/{uname}", icon="chat")],
        [btn("Разместить рекламу", "ad_warning",               icon="megaphone")],
        [btn("Назад",              "about_back",                icon="back")],
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()
