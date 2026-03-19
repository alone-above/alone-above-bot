"""handlers/cart.py — Корзина и избранное"""
from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ae
from db import (
    cart_add, cart_remove, cart_get, cart_clear, cart_has,
    wish_add, wish_remove, wish_get, wish_has, wish_count,
    get_product, parse_sizes, is_banned,
    validate_promo, apply_promo_to_price,
)
from keyboards import kb_main, kb_back, btn, kb
from utils import fmt_price


class CartPromoSt(StatesGroup):
    entering = State()

router = Router()


# ── Корзина ───────────────────────────────────────────
async def _show_cart(uid: int, edit_msg=None, send_fn=None):
    items = await cart_get(uid)
    if not items:
        text = (
            f"{ae('cart')} <b>Корзина пуста</b>\n\n"
            f"<blockquote>Добавьте товары из каталога.</blockquote>"
        )
        markup = kb([btn("В каталог", "shop", icon="shop")],
                    [btn("Назад",     "profile_view", icon="back")])
    else:
        total = sum(i["price"] for i in items)
        lines = []
        for i in items:
            avail = "✅" if i["stock"] > 0 else "❌"
            lines.append(f"• <b>{i['name']}</b>  ({i['size']})  "
                         f"{fmt_price(i['price'])}  {avail}")
        text = (
            f"{ae('cart')} <b>Корзина</b>  ({len(items)} поз.)\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines) +
            f"\n━━━━━━━━━━━━━━━━━\n"
            f"{ae('money')} <b>Итого:</b> {fmt_price(total)}"
        )
        rows = []
        for i in items:
            rows.append([
                btn(i["name"][:20], f"prod_{i['product_id']}", icon="bag"),
                btn("Убрать", f"cart_rm_{i['product_id']}_{i['size']}", icon="delete"),
            ])
        rows.append([btn("Оформить заказ", "cart_checkout",      icon="ok")])
        rows.append([btn("Очистить",       "cart_clear_confirm", icon="delete")])
        rows.append([btn("Назад",          "profile_view",       icon="back")])
        markup = kb(*rows)

    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            try:
                await edit_msg.delete()
            except Exception:
                pass
    if send_fn:
        await send_fn(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "my_cart")
async def cb_my_cart(cb: types.CallbackQuery):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await _show_cart(cb.from_user.id, edit_msg=cb.message)
    await cb.answer()


@router.callback_query(F.data == "cart_checkout")
async def cb_cart_checkout(cb: types.CallbackQuery, state: FSMContext):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return

    items = await cart_get(cb.from_user.id)
    if not items:
        await cb.answer("Корзина пуста", show_alert=True)
        await _show_cart(cb.from_user.id, edit_msg=cb.message)
        return

    data = await state.get_data()
    promo_code = data.get("cart_promo_code", "")
    promo_info = data.get("cart_promo_info", "")

    total = sum(i["price"] for i in items)
    discount = 0
    error_line = ""
    if promo_code:
        promo, err = await validate_promo(
            promo_code, cb.from_user.id,
            allowed_types=["cart_discount_percent", "cart_discount_fixed"],
        )
        if promo:
            total, discount, promo_info = apply_promo_to_price(total, promo)
            await state.update_data(
                cart_promo_code=promo_code,
                cart_promo_info=promo_info,
                cart_promo_discount=discount,
            )
        else:
            promo_code = ""
            promo_info = ""
            await state.update_data(cart_promo_code="", cart_promo_info="", cart_promo_discount=0)
            error_line = f"\n⚠️ {err}\n"

    text = (
        f"{ae('cart')} <b>Оформление корзины</b>\n\n"
        f"{ae('money')} <b>Итого:</b> {fmt_price(total)}\n"
        + (f"\n{promo_info}\n" if promo_info else "")
        + (f"\n{ae('promo')} <b>Промокод:</b> <code>{promo_code}</code>\n" if promo_code else "")
        + error_line
        + "\n<blockquote>Выберите способ оплаты. После оплаты всё содержимое корзины будет оформлено как заказ.</blockquote>"
    )

    rows = [
        [btn("CryptoPay (USDT)", "pay_crypto_cart", icon="money")],
        [btn("Kaspi переводом", "pay_kaspi_cart", icon="phone")],
        [btn("Применить промокод", "apply_cart_promo", icon="promo")],
        [btn("Назад", "my_cart", icon="back")],
    ]
    markup = kb(*rows)

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "apply_cart_promo")
async def cb_apply_cart_promo(cb: types.CallbackQuery, state: FSMContext):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await state.set_state(CartPromoSt.entering)
    try:
        await cb.message.edit_text(
            f"{ae('promo')} <b>Введите промокод</b>\n\n"
            f"<blockquote>Введите код купона:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_back("cart_checkout"),
        )
    except Exception:
        await cb.message.answer(
            f"{ae('promo')} <b>Введите промокод</b>",
            parse_mode="HTML",
            reply_markup=kb_back("cart_checkout"),
        )
    await cb.answer()


@router.message(CartPromoSt.entering)
async def proc_cart_promo(msg: types.Message, state: FSMContext):
    code = msg.text.strip().upper()
    if code.lower() in ("удалить", "delete", "clear"):
        await state.update_data(cart_promo_code="", cart_promo_info="", cart_promo_discount=0)
        await state.clear()
        await msg.answer("✅ Промокод удалён.", reply_markup=kb_back("cart_checkout"))
        return

    promo, err = await validate_promo(code, msg.from_user.id, allowed_types=[
        "cart_discount_percent", "cart_discount_fixed",
    ])
    if not promo:
        await msg.answer(f"⚠️ {err}", reply_markup=kb_back("cart_checkout"))
        return

    # Сохраняем активный промокод для корзины.
    await state.update_data(cart_promo_code=code)
    await state.set_state(CartPromoSt.entering)
    await msg.answer(
        f"✅ Промокод <code>{code}</code> принят!\n\n"
        "Вернитесь к оформлению корзины.",
        parse_mode="HTML",
        reply_markup=kb_back("cart_checkout"),
    )


@router.callback_query(F.data.startswith("cart_addsize_"))
async def cb_cart_addsize(cb: types.CallbackQuery):
    parts = cb.data.split("_", 3)
    pid, size = int(parts[2]), parts[3]
    already = await cart_has(cb.from_user.id, pid, size)
    if already:
        await cb.answer("Уже в корзине", show_alert=True)
        return
    await cart_add(cb.from_user.id, pid, size)
    await cb.answer(f"🛒 Добавлено ({size})!")


@router.callback_query(F.data.startswith("cart_rm_"))
async def cb_cart_rm(cb: types.CallbackQuery):
    parts = cb.data.split("_", 3)
    pid, size = int(parts[2]), parts[3]
    await cart_remove(cb.from_user.id, pid, size)
    await cb.answer("Убрано из корзины")
    await _show_cart(cb.from_user.id, edit_msg=cb.message)


@router.callback_query(F.data == "cart_clear_confirm")
async def cb_cart_clear_confirm(cb: types.CallbackQuery):
    markup = kb(
        [btn("Да, очистить", "cart_clear_do", icon="delete")],
        [btn("Отмена",       "my_cart",       icon="back")],
    )
    try:
        await cb.message.edit_text(
            "🗑 <b>Очистить корзину?</b>\n\n"
            "<blockquote>Все товары будут убраны.</blockquote>",
            parse_mode="HTML", reply_markup=markup,
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "cart_clear_do")
async def cb_cart_clear_do(cb: types.CallbackQuery):
    await cart_clear(cb.from_user.id)
    await cb.answer("🗑 Корзина очищена")
    await _show_cart(cb.from_user.id, edit_msg=cb.message)


# ── Избранное ─────────────────────────────────────────
async def _show_wishlist(uid: int, edit_msg=None, send_fn=None):
    items = await wish_get(uid)
    if not items:
        text = (
            f"{ae('heart')} <b>Избранное пусто</b>\n\n"
            f"<blockquote>Добавляйте товары в избранное, нажав {ae('heart')} на странице товара.</blockquote>"
        )
        markup = kb([btn("В каталог", "shop",        icon="shop")],
                    [btn("Назад",     "profile_view", icon="back")])
    else:
        lines = []
        for i in items:
            avail = "✅" if i["stock"] > 0 else "❌"
            lines.append(f"• <b>{i['name']}</b>  {fmt_price(i['price'])}  {avail}")
        text = (
            f"{ae('heart')} <b>Избранное</b>  ({len(items)} товар{'ов' if len(items)>4 else 'а' if len(items)>1 else ''})\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines) +
            f"\n━━━━━━━━━━━━━━━━━"
        )
        rows = []
        for i in items:
            rows.append([
                btn(i["name"][:20], f"prod_{i['product_id']}", icon="bag"),
                btn("Убрать",       f"wish_rm_{i['product_id']}", icon="delete"),
            ])
        rows.append([btn("Назад", "profile_view", icon="back")])
        markup = kb(*rows)

    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            pass
    if send_fn:
        await send_fn(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "my_wishlist")
async def cb_my_wishlist(cb: types.CallbackQuery):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await _show_wishlist(cb.from_user.id, edit_msg=cb.message)
    await cb.answer()


@router.callback_query(F.data.startswith("wish_toggle_"))
async def cb_wish_toggle(cb: types.CallbackQuery):
    pid = int(cb.data.split("_")[2])
    uid = cb.from_user.id
    p   = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    if await wish_has(uid, pid):
        await wish_remove(uid, pid)
        await cb.answer("💔 Убрано из избранного")
    else:
        await wish_add(uid, pid)
        await cb.answer("❤️ Добавлено в избранное!")


@router.callback_query(F.data.startswith("wish_rm_"))
async def cb_wish_rm(cb: types.CallbackQuery):
    pid = int(cb.data.split("_")[2])
    await wish_remove(cb.from_user.id, pid)
    await cb.answer("💔 Убрано из избранного")
    await _show_wishlist(cb.from_user.id, edit_msg=cb.message)
