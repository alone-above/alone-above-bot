"""handlers/partners.py — Партнёрская программа (пользователи)"""
import json
import random
import string
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ae
from db import (
    get_partner, create_partner, get_partner_by_ref,
    get_partner_referrals, update_partner_bonuses,
    get_bot_msg,
)
from keyboards import kb_back, btn, kb
from utils import fmt_price

router = Router()


class PartnerSt(StatesGroup):
    custom_ref  = State()
    bonus_type  = State()


def _gen_ref() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _fmt_buyer_bonus(bonus_cfg: dict) -> str:
    btype = bonus_cfg.get("type", "percent")
    val   = bonus_cfg.get("value", 0)
    if btype == "percent":
        return f"{val}% от суммы заказа"
    elif btype == "fixed":
        return fmt_price(val)
    return str(val)


@router.callback_query(F.data == "partner_program")
async def cb_partner_program(cb: types.CallbackQuery):
    from aiogram import Bot
    uid     = cb.from_user.id
    partner = await get_partner(uid)
    header  = await get_bot_msg("partner_header")

    if partner:
        bot: Bot = cb.bot
        me      = await bot.get_me()
        ref_url = f"https://t.me/{me.username}?start=ref_{partner['ref_code']}"
        try:
            bonus_new    = json.loads(partner["bonus_new"])
            bonus_repeat = json.loads(partner["bonus_repeat"])
        except Exception:
            bonus_new    = {"type": "percent", "value": 5}
            bonus_repeat = {"type": "percent", "value": 3}

        text = (
            f"🤝 <b>Партнёрская программа</b>\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Ваша реф-ссылка:</b>\n<code>{ref_url}</code>\n\n"
            f"👥 <b>Приглашено:</b> {partner['total_invited']}\n"
            f"💰 <b>Заработано:</b> {fmt_price(partner['total_earned'])}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{ae('gift')} <b>Бонус (новые покупатели):</b> {_fmt_buyer_bonus(bonus_new)}\n"
            f"{ae('refresh')} <b>Бонус (повторные):</b> {_fmt_buyer_bonus(bonus_repeat)}\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        markup = kb(
            [btn("Мои приглашённые",  "partner_refs",         icon="users")],
            [btn("Настроить бонусы",  "partner_set_bonuses",  icon="settings")],
            [btn("Назад",             "profile_view",          icon="back")],
        )
    else:
        text = (
            f"{header}\n\n━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>Зарегистрируйтесь как партнёр "
            f"и получайте бонусы за каждого приглашённого покупателя!</blockquote>"
        )
        markup = kb(
            [btn("Стать партнёром", "become_partner", icon="rocket")],
            [btn("Назад",           "profile_view",   icon="back")],
        )

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "become_partner")
async def cb_become_partner(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(PartnerSt.custom_ref)
    markup = kb(
        [btn("Сгенерировать автоматически", "partner_autoref",  icon="sparkle")],
        [btn("Ввести свой код",             "partner_customref", icon="edit")],
        [btn("Назад",                        "partner_program",  icon="back")],
    )
    try:
        await cb.message.edit_text(
            "🔗 <b>Создание реф-ссылки</b>\n\n"
            "<blockquote>Выберите тип реферального кода:</blockquote>",
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer(
            "🔗 <b>Создание реф-ссылки</b>", parse_mode="HTML", reply_markup=markup
        )
    await cb.answer()


@router.callback_query(F.data == "partner_autoref")
async def cb_partner_autoref(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    # Генерируем уникальный код
    for _ in range(10):
        code = _gen_ref()
        existing = await get_partner_by_ref(code)
        if not existing:
            break
    ok = await create_partner(uid, code)
    if not ok:
        await cb.answer("Не удалось создать реф-ссылку. Попробуйте снова.", show_alert=True)
        return
    from aiogram import Bot
    me  = await cb.bot.get_me()
    url = f"https://t.me/{me.username}?start=ref_{code}"
    markup = kb([btn("Партнёрская программа", "partner_program", icon="partner")])
    try:
        await cb.message.edit_text(
            f"{ae('confetti')} <b>Реф-ссылка создана!</b>\n\n"
            f"<code>{url}</code>\n\n"
            f"<blockquote>Делитесь этой ссылкой и получайте бонусы за каждого покупателя.</blockquote>",
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer(
            f"{ae('confetti')} <b>Реф-ссылка:</b>\n<code>{url}</code>",
            parse_mode="HTML", reply_markup=markup,
        )
    await cb.answer()


@router.callback_query(F.data == "partner_customref")
async def cb_partner_customref(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(PartnerSt.custom_ref)
    try:
        await cb.message.edit_text(
            "✏️ <b>Введите свой реф-код</b>\n\n"
            "<blockquote>Только латинские буквы и цифры, 4–12 символов.\n"
            "Пример: SHOP2024</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_back("become_partner"),
        )
    except Exception:
        await cb.message.answer(
            "✏️ <b>Введите реф-код</b>", parse_mode="HTML",
            reply_markup=kb_back("become_partner"),
        )
    await cb.answer()


@router.message(PartnerSt.custom_ref)
async def proc_custom_ref(msg: types.Message, state: FSMContext):
    code = msg.text.strip().upper()
    if not code.isalnum() or not (4 <= len(code) <= 12):
        await msg.answer("❌ Код должен содержать только буквы/цифры (4–12 символов).")
        return
    ok = await create_partner(msg.from_user.id, code)
    if not ok:
        await msg.answer("❌ Этот код уже занят. Выберите другой.")
        return
    await state.clear()
    me  = await msg.bot.get_me()
    url = f"https://t.me/{me.username}?start=ref_{code}"
    from keyboards import kb_main
    await msg.answer(
        f"{ae('confetti')} <b>Реф-ссылка создана!</b>\n\n<code>{url}</code>",
        parse_mode="HTML", reply_markup=kb_main(),
    )


@router.callback_query(F.data == "partner_refs")
async def cb_partner_refs(cb: types.CallbackQuery):
    partner = await get_partner(cb.from_user.id)
    if not partner:
        await cb.answer("Вы не являетесь партнёром", show_alert=True)
        return
    refs = await get_partner_referrals(partner["user_id"], limit=20)
    if not refs:
        await cb.answer("Приглашённых пока нет", show_alert=True)
        return

    lines = []
    for r in refs[:20]:
        name = f"@{r['username']}" if r.get("username") else r.get("first_name", "—")
        kind = "🆕" if r["is_new_buyer"] else "🔄"
        lines.append(f"{kind} {name}  +{fmt_price(r['bonus_amount'])}")
    text = (
        f"👥 <b>Мои приглашённые</b> ({len(refs)})\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines[:15]) +
        f"\n━━━━━━━━━━━━━━━━━"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_back("partner_program"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML",
                                reply_markup=kb_back("partner_program"))
    await cb.answer()


@router.callback_query(F.data == "partner_set_bonuses")
async def cb_partner_set_bonuses(cb: types.CallbackQuery):
    markup = kb(
        [btn("% от суммы",   "pbtype_percent", icon="stats")],
        [btn("Фикс. сумма",  "pbtype_fixed",   icon="money")],
        [btn("Назад",         "partner_program", icon="back")],
    )
    try:
        await cb.message.edit_text(
            "⚙️ <b>Тип бонуса для покупателей</b>\n\n"
            "<blockquote>Выберите как партнёры будут получать бонус:</blockquote>",
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        await cb.message.answer(
            "⚙️ <b>Тип бонуса</b>", parse_mode="HTML", reply_markup=markup
        )
    await cb.answer()
