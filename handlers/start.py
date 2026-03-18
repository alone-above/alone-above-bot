"""handlers/start.py — /start, /admin, соглашение, главное меню"""
from aiogram import Bot, Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, BotCommandScopeChat, ReplyKeyboardRemove

from config import ADMIN_IDS, SHOP_NAME, ae
from db import (
    ensure_user, is_banned, has_agreed_terms, set_agreed_terms,
    get_bot_msg, get_partner_by_ref, log_event, db_run,
    _cache_invalidate,
)
from keyboards import kb_main, kb_admin, kb_agreement
from utils import fmt_price

router = Router()


# ── Вспомогательная отправка с медиа ─────────────────
async def send_media(bot: Bot, chat_id: int, text: str, key: str, markup=None):
    from db import get_media
    m = await get_media(key)
    if m:
        mt = m["media_type"]
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
            from db import db_run as _dr, _cache_invalidate as _ci
            await _dr("DELETE FROM media_settings WHERE key=$1", (key,))
            _ci(f"media:{key}")
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)


async def set_cmds(bot: Bot, uid: int):
    cmds = [BotCommand(command="start", description="🚀 Старт")]
    if uid in ADMIN_IDS:
        cmds.append(BotCommand(command="admin", description="🎩 Панель"))
    await bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=uid))


# ── /start ────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    await ensure_user(msg.from_user)
    await set_cmds(bot, msg.from_user.id)

    if await is_banned(msg.from_user.id):
        await msg.answer("🚫 Вы заблокированы в этом боте.")
        return

    args    = msg.text.split(maxsplit=1)
    ref_arg = args[1].strip() if len(args) > 1 else ""

    if ref_arg.lower() == "support":
        from handlers.support import show_support
        await show_support(bot, msg.chat.id)
        return

    if ref_arg.startswith("ref_"):
        ref_code = ref_arg[4:].upper()
        partner  = await get_partner_by_ref(ref_code)
        if partner and partner["user_id"] != msg.from_user.id:
            await db_run(
                "UPDATE users SET ref_code=$1 WHERE user_id=$2",
                (ref_code, msg.from_user.id),
            )
            _cache_invalidate(f"user:{msg.from_user.id}")

    if not await has_agreed_terms(msg.from_user.id):
        await _show_agreement(bot, msg.chat.id)
        return

    await log_event("start", msg.from_user.id)
    welcome_text = await get_bot_msg("welcome")
    text = welcome_text.replace("{shop_name}", SHOP_NAME)
    full_text = (
        f"{ae('sparkle')} <b>{SHOP_NAME}</b>\n\n"
        f"<blockquote>{ae('down')} {text}</blockquote>"
    )
    await send_media(bot, msg.chat.id, full_text, "main_menu", kb_main())


# ── /admin ────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(msg: types.Message, state: FSMContext, bot: Bot):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await send_media(
        bot, msg.chat.id,
        f"{ae('crown')} <b>Панель управления</b>",
        "admin_panel", kb_admin(),
    )


# ── Кнопка «Главное меню» ─────────────────────────────
@router.callback_query(F.data == "main")
async def cb_main(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    text = (
        f"{ae('sparkle')} <b>{SHOP_NAME}</b>\n\n"
        f"<blockquote>{ae('down')} Выберите нужный раздел:</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb_main())
    except Exception:
        # Если редактирование не прошло (например, сообщение было удалено),
        # отправляем новое сообщение, чтобы у пользователя оставались кнопки.
        await bot.send_message(cb.from_user.id, text, parse_mode="HTML", reply_markup=kb_main())
    await cb.answer()


# ── Панель администратора (callback) ─────────────────
@router.callback_query(F.data == "adm_panel")
async def cb_adm_panel(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    try:
        await cb.message.edit_text(
            f"{ae('crown')} <b>Панель управления</b>",
            parse_mode="HTML", reply_markup=kb_admin(),
        )
    except Exception:
        await bot.send_message(cb.from_user.id,
                               f"{ae('crown')} <b>Панель управления</b>",
                               parse_mode="HTML", reply_markup=kb_admin())
    await cb.answer()


# ── Соглашение ────────────────────────────────────────
async def _show_agreement(bot: Bot, chat_id: int):
    text = (
        f"👋 <b>Добро пожаловать в {SHOP_NAME}!</b>\n\n"
        f"<blockquote>Перед тем как начать, ознакомьтесь с документами "
        f"и подтвердите согласие:\n\n"
        f"📄 <b>Публичная оферта</b>\n"
        f"📋 <b>Политика конфиденциальности</b>\n"
        f"📝 <b>Пользовательское соглашение</b>\n\n"
        f"Нажимая <b>«Принять и продолжить»</b>, вы подтверждаете согласие.</blockquote>"
    )
    await bot.send_message(chat_id, text, parse_mode="HTML",
                           reply_markup=kb_agreement())


@router.callback_query(F.data == "agree_terms")
async def cb_agree_terms(cb: types.CallbackQuery, bot: Bot):
    await ensure_user(cb.from_user)
    await set_agreed_terms(cb.from_user.id)
    await set_cmds(bot, cb.from_user.id)
    text = (
        f"{ae('shop')} <b>{SHOP_NAME}</b>\n\n"
        f"<blockquote>{ae('ok')} Спасибо! Вы приняли условия.\n\n"
        f"{ae('down')} Выберите раздел:</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb_main())
    except Exception:
        await bot.send_message(cb.from_user.id, text, parse_mode="HTML", reply_markup=kb_main())
    await cb.answer("✅ Добро пожаловать!")
