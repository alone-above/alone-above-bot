"""handlers/payment.py — Покупка, промокод, оплата (Crypto / Kaspi)"""
import json
import time
from datetime import datetime

from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ae, KASPI_PHONE, MANAGER_ID, ADMIN_IDS
from db import (
    cart_get, cart_clear,
    get_product, get_user, ensure_user, parse_sizes,
    get_usd_kzt_rate, kzt_to_usd, create_invoice,
    save_crypto, get_crypto, set_crypto_paid,
    save_kaspi, get_kaspi, set_kaspi_status,
    create_order, set_order_status,
    add_purchase, add_bonus, reduce_stock,
    validate_promo, apply_promo_to_price, use_promo,
    is_banned, log_event,
    db_run, db_one,
)

# Compatibility: some deployments may ship an older `db` package that does not export
# `save_cart_crypto`, `get_cart_crypto`, `set_cart_crypto_paid`.
try:
    from db.payments import save_cart_crypto, get_cart_crypto, set_cart_crypto_paid
except (ImportError, ModuleNotFoundError):
    async def save_cart_crypto(uid, inv_id, amount_kzt, amount_usd, items: list,
                                promo_code: str = "", discount: float = 0):
        try:
            payload = {
                "items": items,
                "promo_code": promo_code,
                "discount": discount,
            }
            await db_run(
                """INSERT INTO cart_crypto_payments
                   (user_id,invoice_id,amount_kzt,amount_usd,items,created_at)
                   VALUES($1,$2,$3,$4,$5,$6)""",
                (uid, inv_id, amount_kzt, amount_usd, json.dumps(payload), datetime.now().isoformat()),
            )
        except Exception:
            pass

    async def get_cart_crypto(inv_id: str):
        rec = await db_one("SELECT * FROM cart_crypto_payments WHERE invoice_id=$1", (inv_id,))
        if rec and rec.get("items"):
            try:
                payload = json.loads(rec["items"])
                # legacy support: if the stored value is a plain list of items
                if isinstance(payload, list):
                    rec["items"] = payload
                    rec["promo_code"] = ""
                    rec["discount"] = 0
                else:
                    rec["items"] = payload.get("items")
                    rec["promo_code"] = payload.get("promo_code")
                    rec["discount"] = payload.get("discount")
            except Exception:
                pass
        return rec

    async def set_cart_crypto_paid(inv_id: str):
        await db_run(
            "UPDATE cart_crypto_payments SET status='paid' WHERE invoice_id=$1", (inv_id,)
        )

from keyboards import kb_main, kb_back, btn, kb, kb_payment
from utils import fmt_price

router = Router()


class PromoApplySt(StatesGroup):
    entering = State()

class OrderNoteSt(StatesGroup):
    entering = State()


# ── Выбор размера ─────────────────────────────────────
@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: types.CallbackQuery):
    pid = int(cb.data.split("_")[1])
    p   = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    if p["stock"] <= 0:
        await cb.answer("😔 Товар закончился", show_alert=True)
        return
    sizes = parse_sizes(p)
    if not sizes:
        await _show_payment_confirm(cb, pid, "ONE_SIZE")
        return
    rows = [[btn(s, f"size_{pid}_{s}")] for s in sizes]
    rows.append([btn("Назад", f"prod_{pid}", icon="back")])
    text = (
        f"{ae('size')} <b>Выберите размер</b>\n\n"
        f"<blockquote>Товар: <b>{p['name']}</b></blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb(*rows))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb(*rows))
    await cb.answer()


@router.callback_query(F.data.startswith("size_"))
async def cb_size(cb: types.CallbackQuery):
    parts       = cb.data.split("_", 2)
    pid, size   = int(parts[1]), parts[2]
    await _show_payment_confirm(cb, pid, size)


# ── Страница подтверждения оплаты ─────────────────────
async def _show_payment_confirm(
    cb: types.CallbackQuery, pid: int, size: str,
    promo=None, promo_error: str = "",
):
    p = await get_product(pid)
    if not p:
        await cb.answer("Товар не найден", show_alert=True)
        return
    await ensure_user(cb.from_user)
    user  = await get_user(cb.from_user.id)
    rate  = await get_usd_kzt_rate()
    price = p["price"]
    discount  = 0
    promo_line = ""
    if promo:
        price, discount, info = apply_promo_to_price(p["price"], promo)
        promo_line = f"\n🎟 <b>Промокод:</b> <code>{promo['code']}</code>\n  ✅ {info}\n"

    usd_amt = kzt_to_usd(price, rate)
    phone   = user["phone"] if user["phone"] else None
    address = user["default_address"] if user["default_address"] else None
    phone_s   = f"<code>{phone}</code>" if phone else "<i>не указан ❗</i>"
    address_s = f"<i>{address}</i>"   if address else "<i>не указан ❗</i>"
    error_line = f"\n⚠️ {promo_error}\n" if promo_error else ""

    text = (
        f"🛍 <b>Оформление заказа</b>\n\n"
        f"{ae('box')} {p['name']}  ({size})\n"
        f"{ae('money')} <b>Цена:</b> <code>{fmt_price(p['price'])}</code>"
    )
    if discount > 0:
        text += f" → <code>{fmt_price(price)}</code>"
    text += (
        f" (~{usd_amt} USDT)\n"
        f"{promo_line}{error_line}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{ae('phone')} <b>Телефон:</b> {phone_s}\n"
        f"{ae('pin')} <b>Адрес:</b> {address_s}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>Выберите способ оплаты:</blockquote>"
    )

    promo_code = promo["code"] if promo else ""
    markup = kb_payment(pid, size, promo_code)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


# ── Промокод ──────────────────────────────────────────
@router.callback_query(F.data.startswith("apply_promo_"))
async def cb_apply_promo(cb: types.CallbackQuery, state: FSMContext):
    parts = cb.data.split("_", 3)
    pid, size = int(parts[2]), parts[3]
    await state.update_data(promo_pid=pid, promo_size=size)
    await state.set_state(PromoApplySt.entering)
    try:
        await cb.message.edit_text(
            f"{ae('promo')} <b>Введите промокод</b>\n\n"
            f"<blockquote>Введите код купона:</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_back(f"size_{pid}_{size}"),
        )
    except Exception:
        await cb.message.answer(
            f"{ae('promo')} <b>Введите промокод</b>",
            parse_mode="HTML",
            reply_markup=kb_back(f"size_{pid}_{size}"),
        )
    await cb.answer()


@router.message(PromoApplySt.entering)
async def proc_promo(msg: types.Message, state: FSMContext):
    d    = await state.get_data()
    pid  = d.get("promo_pid")
    size = d.get("promo_size", "ONE_SIZE")
    code = msg.text.strip().upper()
    await state.clear()

    promo, err = await validate_promo(code, msg.from_user.id)
    if promo and promo["promo_type"].startswith("cart_"):
        promo = None
        err = "❌ Этот промокод работает только при оплате корзины."

    # Создаём фиктивный callback для переиспользования _show_payment_confirm
    class _FakeCb:
        from_user = msg.from_user
        message   = msg
        async def answer(self, *a, **kw): pass

    await _show_payment_confirm(_FakeCb(), pid, size,
                                promo=promo, promo_error=err)


# ── CryptoPay ─────────────────────────────────────────
@router.callback_query(F.data == "pay_crypto_cart")
async def cb_pay_crypto_cart(cb: types.CallbackQuery, bot: Bot, state: FSMContext):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return

    items = await cart_get(cb.from_user.id)
    if not items:
        await cb.answer("Корзина пуста", show_alert=True)
        return

    # Проверяем наличие товара
    for i in items:
        if i["stock"] <= 0:
            await cb.answer("Один из товаров в корзине закончился", show_alert=True)
            return

    data = await state.get_data()
    promo_code = data.get("cart_promo_code", "")
    discount = data.get("cart_promo_discount", 0)

    total_kzt = sum(i["price"] for i in items)
    if discount:
        total_kzt = max(total_kzt - discount, 0)

    rate      = await get_usd_kzt_rate()
    total_usd = kzt_to_usd(total_kzt, rate)

    me = await bot.get_me()
    invoice = await create_invoice(
        total_usd,
        "Заказ из корзины",
        f"cart_{cb.from_user.id}_{int(time.time())}",
        me.username,
    )
    if not invoice:
        await cb.answer("❌ Ошибка создания счёта. Попробуйте позже.", show_alert=True)
        return

    # Сохраняем информацию о корзине для проверки оплаты
    items_data = [
        {"product_id": i["product_id"], "size": i["size"], "price": i["price"]}
        for i in items
    ]
    await save_cart_crypto(
        cb.from_user.id,
        invoice["invoice_id"],
        total_kzt,
        total_usd,
        items_data,
        promo_code=promo_code,
        discount=discount,
    )

    markup = kb(
        [btn("Оплатить в CryptoPay", url=invoice["bot_invoice_url"], icon="money")],
        [btn("Проверить оплату", f"check_crypto_{invoice['invoice_id']}", icon="refresh")],
        [btn("Назад", "my_cart", icon="back")],
    )
    text = (
        f"{ae('money')} <b>Оплата через CryptoPay</b>\n\n"
        f"<b>Всего товаров</b>: {len(items)}\n"
        f"💵 <b>Сумма:</b> {total_usd} USDT (~{fmt_price(total_kzt)})\n\n"
        f"<blockquote>Нажмите «Оплатить», завершите платёж, "
        f"затем нажмите «Проверить оплату».</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data == "pay_kaspi_cart")
async def cb_pay_kaspi_cart(cb: types.CallbackQuery, state: FSMContext):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return

    items = await cart_get(cb.from_user.id)
    if not items:
        await cb.answer("Корзина пуста", show_alert=True)
        return

    # Проверяем наличие товара
    for i in items:
        if i["stock"] <= 0:
            await cb.answer("Один из товаров в корзине закончился", show_alert=True)
            return

    data = await state.get_data()
    promo_code = data.get("cart_promo_code", "")
    discount = data.get("cart_promo_discount", 0)

    # Сохраняем состояние для оформления корзины через Kaspi
    await state.update_data(
        kaspi_cart=True,
        kaspi_cart_items=[
            {"product_id": i["product_id"], "size": i["size"], "price": i["price"]}
            for i in items
        ],
        kaspi_promo=promo_code,
        kaspi_discount=discount,
    )
    await state.set_state(OrderNoteSt.entering)

    text = (
        f"{ae('phone')} <b>Оплата через Kaspi</b>\n\n"
        f"{ae('money')} <b>Итого:</b> <code>{fmt_price(sum(i['price'] for i in items) - discount)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📲 Переведите <b>{fmt_price(sum(i['price'] for i in items) - discount)}</b> на номер:\n"
        f"<code>{KASPI_PHONE}</code>\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>Напишите примечание к заказу (адрес доставки, пожелания) "
        f"или отправьте <b>—</b> если нет примечаний.</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb_back("cart_checkout"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb_back("cart_checkout"))
    await cb.answer()


@router.callback_query(F.data.startswith("pay_crypto_"))
async def cb_pay_crypto(cb: types.CallbackQuery, bot: Bot):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    raw        = cb.data[len("pay_crypto_"):]
    parts      = raw.split("_", 2)
    pid, size  = int(parts[0]), parts[1]
    promo_code = parts[2] if len(parts) > 2 else ""

    p = await get_product(pid)
    if not p or p["stock"] <= 0:
        await cb.answer("Товар недоступен", show_alert=True)
        return

    promo = None
    if promo_code:
        promo, _ = await validate_promo(promo_code, cb.from_user.id)
        if promo and promo["promo_type"].startswith("cart_"):
            promo = None

    rate     = await get_usd_kzt_rate()
    price    = p["price"]
    discount = 0
    if promo:
        price, discount, _ = apply_promo_to_price(price, promo)

    usd_amt = kzt_to_usd(price, rate)
    me      = await bot.get_me()
    invoice = await create_invoice(
        usd_amt,
        f"Заказ: {p['name']} ({size})",
        f"order_{cb.from_user.id}_{pid}_{size}",
        me.username,
    )
    if not invoice:
        await cb.answer("❌ Ошибка создания счёта. Попробуйте позже.", show_alert=True)
        return

    await save_crypto(cb.from_user.id, pid, size, invoice["invoice_id"],
                      price, usd_amt, promo_code, discount)

    markup = kb(
        [btn("Оплатить в CryptoPay", url=invoice["bot_invoice_url"], icon="money")],
        [btn("Проверить оплату", f"check_crypto_{invoice['invoice_id']}", icon="refresh")],
        [btn("Назад", f"prod_{pid}", icon="back")],
    )
    text = (
        f"{ae('money')} <b>Оплата через CryptoPay</b>\n\n"
        f"{ae('box')} {p['name']} ({size})\n"
        f"💵 <b>Сумма:</b> {usd_amt} USDT (~{fmt_price(price)})\n\n"
        f"<blockquote>Нажмите «Оплатить», завершите платёж, "
        f"затем нажмите «Проверить оплату».</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await cb.answer()


@router.callback_query(F.data.startswith("check_crypto_"))
async def cb_check_crypto(cb: types.CallbackQuery, bot: Bot):
    inv_id  = cb.data[len("check_crypto_"):]
    inv     = await check_invoice(inv_id)
    rec     = await __import__("db").get_crypto(inv_id)
    is_cart = False

    if not rec:
        rec = await __import__("db").get_cart_crypto(inv_id)
        is_cart = True if rec else False

    if not inv or not rec:
        await cb.answer("❌ Платёж не найден", show_alert=True)
        return
    if inv.get("status") != "paid":
        await cb.answer("⏳ Оплата ещё не поступила. Повторите проверку.", show_alert=True)
        return

    # Оформляем покупку
    if is_cart:
        await set_cart_crypto_paid(inv_id)

        items = rec.get("items") or []
        promo_code = rec.get("promo_code") or ""
        discount = rec.get("discount") or 0
        total_kzt = sum(i.get("price", 0) for i in items)
        total_kzt_after = max(total_kzt - discount, 0)

        user = await get_user(rec["user_id"])
        uname = user["username"] if user else ""
        fname = user["first_name"] if user else ""
        phone = user["phone"] if user else ""
        addr  = user["default_address"] if user else ""

        # Распределяем скидку по товарам (пропорционально цене)
        remaining_disc = discount
        orders = []
        for idx, item in enumerate(items):
            pid = item.get("product_id")
            size = item.get("size")
            item_price = item.get("price", 0)
            if idx == len(items) - 1:
                item_discount = remaining_disc
            else:
                item_discount = round(discount * (item_price / total_kzt), 0) if total_kzt else 0
                remaining_disc -= item_discount
            item_price_final = max(item_price - item_discount, 0)

            oid = await create_order(
                rec["user_id"], uname, fname,
                pid, size, item_price_final, "crypto",
                phone, addr, promo_code, item_discount,
            )
            if oid:
                await set_order_status(oid, "processing")
                await add_purchase(rec["user_id"], pid, item_price_final, "crypto")
                await reduce_stock(pid)
                orders.append(oid)

        bonus = await add_bonus(rec["user_id"], total_kzt_after)

        if promo_code and orders:
            promo, _ = await validate_promo(promo_code, rec["user_id"])
            if promo:
                await use_promo(rec["user_id"], promo["id"], orders[0])

        await cart_clear(rec["user_id"])
        await log_event("purchase_crypto_cart", rec["user_id"], str(orders))

        # Уведомление менеджеру
        prod_lines = []
        for item in items:
            p = await get_product(item.get("product_id"))
            pname = p["name"] if p else "—"
            prod_lines.append(f"{pname} ({item.get('size')})")

        for aid in ADMIN_IDS:
            try:
                await bot.send_message(
                    aid,
                    f"{ae('confetti')} <b>Новый заказ (Crypto, корзина)</b>\n\n"
                    f"{ae('user')} <a href='tg://user?id={rec['user_id']}'>"
                    f"{user['first_name'] if user else rec['user_id']}</a>\n"
                    f"{ae('box')} {len(items)} позиций:\n" + "\n".join(prod_lines) + "\n"
                    f"{ae('money')} {fmt_price(total_kzt_after)}\n"
                    f"{ae('coin')} Бонус: {fmt_price(bonus)}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await cb.message.edit_text(
            f"{ae('confetti')} <b>Оплата подтверждена!</b>\n\n"
            f"<blockquote>Заказ оформлен.\n"
            f"Бонус: <b>{fmt_price(bonus)}</b> начислен на счёт.</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_main(),
        )
        await cb.answer("✅ Оплата принята!")
        return

    # Single-item purchase
    await set_crypto_paid(inv_id)
    p       = await get_product(rec["product_id"])
    user    = await get_user(rec["user_id"])
    oid = await create_order(
        rec["user_id"], user["username"] if user else "",
        user["first_name"] if user else "",
        rec["product_id"], rec["size"], rec["amount_kzt"],
        "crypto", user["phone"] if user else "",
        user["default_address"] if user else "",
        rec["promo_code"], rec["discount"],
    )
    await set_order_status(oid, "processing")
    await add_purchase(rec["user_id"], rec["product_id"], rec["amount_kzt"], "crypto")
    await reduce_stock(rec["product_id"])
    bonus = await add_bonus(rec["user_id"], rec["amount_kzt"])

    if rec.get("promo_code"):
        promo, _ = await validate_promo(rec["promo_code"], rec["user_id"])
        if promo:
            await use_promo(rec["user_id"], promo["id"], oid)

    await log_event("purchase_crypto", rec["user_id"], str(oid))

    # Уведомление менеджеру
    pname = p["name"] if p else "—"
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                f"{ae('confetti')} <b>Новый заказ #{oid} (Crypto)</b>\n\n"
                f"{ae('user')} <a href='tg://user?id={rec['user_id']}'>"
                f"{user['first_name'] if user else rec['user_id']}</a>\n"
                f"{ae('box')} {pname} ({rec['size']})\n"
                f"{ae('money')} {fmt_price(rec['amount_kzt'])}\n"
                f"{ae('coin')} Бонус начислен: {fmt_price(bonus)}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.message.edit_text(
        f"{ae('confetti')} <b>Оплата подтверждена!</b>\n\n"
        f"<blockquote>Заказ <b>#{oid}</b> оформлен.\n"
        f"Бонус: <b>{fmt_price(bonus)}</b> начислен на счёт.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
    await cb.answer("✅ Оплата принята!")


# ── Kaspi ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("pay_kaspi_"))
async def cb_pay_kaspi(cb: types.CallbackQuery, state: FSMContext):
    if await is_banned(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    raw        = cb.data[len("pay_kaspi_"):]
    parts      = raw.split("_", 2)
    pid, size  = int(parts[0]), parts[1]
    promo_code = parts[2] if len(parts) > 2 else ""

    p = await get_product(pid)
    if not p or p["stock"] <= 0:
        await cb.answer("Товар недоступен", show_alert=True)
        return

    promo = None
    if promo_code:
        promo, _ = await validate_promo(promo_code, cb.from_user.id)
        if promo and promo["promo_type"].startswith("cart_"):
            promo = None

    price    = p["price"]
    discount = 0
    if promo:
        price, discount, _ = apply_promo_to_price(price, promo)

    await state.update_data(kaspi_pid=pid, kaspi_size=size,
                            kaspi_price=price, kaspi_discount=discount,
                            kaspi_promo=promo_code)
    await state.set_state(OrderNoteSt.entering)

    text = (
        f"{ae('phone')} <b>Оплата через Kaspi</b>\n\n"
        f"{ae('box')} {p['name']} ({size})\n"
        f"{ae('money')} <b>Сумма:</b> <code>{fmt_price(price)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📲 Переведите <b>{fmt_price(price)}</b> на номер:\n"
        f"<code>{KASPI_PHONE}</code>\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>Напишите примечание к заказу "
        f"(адрес доставки, размер, пожелания) "
        f"или отправьте <b>—</b> если нет примечаний.</blockquote>"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML",
                                   reply_markup=kb_back(f"prod_{pid}"))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML",
                                reply_markup=kb_back(f"prod_{pid}"))
    await cb.answer()


@router.message(OrderNoteSt.entering)
async def proc_order_note(msg: types.Message, state: FSMContext, bot: Bot):
    d          = await state.get_data()
    pid        = d["kaspi_pid"]
    size       = d["kaspi_size"]
    price      = d["kaspi_price"]
    discount   = d.get("kaspi_discount", 0)
    promo_code = d.get("kaspi_promo", "")
    note       = msg.text.strip() if msg.text.strip() != "—" else ""
    await state.clear()

    p    = await get_product(pid)
    user = await get_user(msg.from_user.id)
    kid  = await save_kaspi(
        msg.from_user.id, pid, size, price, promo_code, discount, note
    )
    oid = await create_order(
        msg.from_user.id,
        user["username"] if user else "",
        user["first_name"] if user else "",
        pid, size, price, "kaspi",
        user["phone"] if user else "",
        user["default_address"] if user else "",
        promo_code, discount,
    )

    pname = p["name"] if p else "—"
    uname = f"@{msg.from_user.username}" if msg.from_user.username else str(msg.from_user.id)
    notif = (
        f"{ae('bell')} <b>Новый заказ #{oid} (Kaspi)</b>\n\n"
        f"{ae('user')} {uname} ({msg.from_user.first_name})\n"
        f"🆔 <code>{msg.from_user.id}</code>\n"
        f"{ae('box')} {pname} ({size})\n"
        f"{ae('money')} {fmt_price(price)}\n"
        f"📝 {note or '—'}\n\n"
        f"<blockquote>Подтвердите оплату:</blockquote>"
    )
    mgr_markup = kb(
        [btn("✅ Подтвердить оплату", f"kaspi_confirm_{kid}_{oid}", icon="ok")],
        [btn("❌ Отклонить",          f"kaspi_reject_{kid}_{oid}",  icon="no")],
    )

    mgr_mid = None
    try:
        sent    = await bot.send_message(MANAGER_ID, notif, parse_mode="HTML",
                                         reply_markup=mgr_markup)
        mgr_mid = sent.message_id
    except Exception:
        pass
    if mgr_mid:
        await set_kaspi_status(kid, "pending", mgr_mid)

    await msg.answer(
        f"{ae('ok')} <b>Заказ #{oid} принят!</b>\n\n"
        f"<blockquote>Менеджер проверит оплату и подтвердит заказ.</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


@router.callback_query(F.data.startswith("kaspi_confirm_"))
async def cb_kaspi_confirm(cb: types.CallbackQuery, bot: Bot):
    if cb.from_user.id != MANAGER_ID and cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    parts = cb.data.split("_")
    kid, oid = int(parts[2]), int(parts[3])

    rec  = await __import__("db").get_kaspi(kid)
    if not rec:
        await cb.answer("Запись не найдена", show_alert=True)
        return

    await set_kaspi_status(kid, "confirmed")
    await set_order_status(oid, "processing", cb.from_user.id)
    await add_purchase(rec["user_id"], rec["product_id"], rec["amount"], "kaspi")
    await reduce_stock(rec["product_id"])
    bonus = await add_bonus(rec["user_id"], rec["amount"])

    if rec.get("promo_code"):
        promo, _ = await validate_promo(rec["promo_code"], rec["user_id"])
        if promo:
            await use_promo(rec["user_id"], promo["id"], oid)

    try:
        await bot.send_message(
            rec["user_id"],
            f"{ae('confetti')} <b>Оплата подтверждена!</b>\n\n"
            f"<blockquote>Заказ <b>#{oid}</b> оформлен.\n"
            f"Бонус: <b>{fmt_price(bonus)}</b> начислен на счёт.</blockquote>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await cb.answer("✅ Подтверждено")
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n✅ <b>ПОДТВЕРЖДЕНО</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("kaspi_reject_"))
async def cb_kaspi_reject(cb: types.CallbackQuery, bot: Bot):
    if cb.from_user.id != MANAGER_ID and cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    parts = cb.data.split("_")
    kid, oid = int(parts[2]), int(parts[3])
    rec  = await __import__("db").get_kaspi(kid)
    if not rec:
        await cb.answer("Запись не найдена", show_alert=True)
        return

    await set_kaspi_status(kid, "rejected")
    await set_order_status(oid, "rejected", cb.from_user.id)

    try:
        await bot.send_message(
            rec["user_id"],
            f"{ae('no')} <b>Оплата не подтверждена.</b>\n\n"
            f"<blockquote>Заказ #{oid} отклонён. "
            f"Если это ошибка — обратитесь в поддержку.</blockquote>",
            parse_mode="HTML",
            reply_markup=kb_main(),
        )
    except Exception:
        pass

    await cb.answer("❌ Отклонено")
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass


# WebApp order confirmation/rejection handlers
@router.callback_query(F.data.startswith("weborder_confirm_"))
async def cb_weborder_confirm(cb: types.CallbackQuery, bot: Bot):
    if cb.from_user.id != MANAGER_ID and cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(cb.data.split("_")[-1])
    
    try:
        order = await __import__("db.orders", fromlist=["get_order"]).get_order(order_id)
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        
        # Update order status
        await set_order_status(order_id, "processing", cb.from_user.id)
        
        # Add purchase to user profile (if needed)
        try:
            user_id = order.get("user_id")
            if user_id:
                await __import__("db.users", fromlist=["add_purchase"]).add_purchase(user_id, order.get("amount", 0))
                await __import__("db.users", fromlist=["add_bonus"]).add_bonus(user_id, int(order.get("amount", 0) * 0.05))
        except Exception:
            pass
        
        await cb.answer("✅ Подтверждено")
        try:
            await cb.message.edit_text(
                cb.message.html_text + "\n\n✅ <b>ПОДТВЕРЖДЕНО</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
            
    except Exception as e:
        await cb.answer(f"Ошибка: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.startswith("weborder_reject_"))
async def cb_weborder_reject(cb: types.CallbackQuery, bot: Bot):
    if cb.from_user.id != MANAGER_ID and cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(cb.data.split("_")[-1])
    
    try:
        order = await __import__("db.orders", fromlist=["get_order"]).get_order(order_id)
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        
        # Update order status to rejected
        await set_order_status(order_id, "rejected", cb.from_user.id)
        
        await cb.answer("❌ Отклонено")
        try:
            await cb.message.edit_text(
                cb.message.html_text + "\n\n❌ <b>ОТКЛОНЕНО</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
            
    except Exception as e:
        await cb.answer(f"Ошибка: {str(e)[:50]}", show_alert=True)
