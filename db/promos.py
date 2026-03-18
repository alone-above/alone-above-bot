"""db/promos.py — Промокоды"""
from datetime import datetime
from config import PROMO_TYPES  # noqa: F401 (re-exported for convenience)
from .pool import db_one, db_all, db_run, db_insert
from utils.fmt import fmt_price


async def get_all_promos(active_only: bool = True) -> list:
    if active_only:
        return await db_all(
            "SELECT * FROM promocodes WHERE is_active=1 ORDER BY created_at DESC"
        )
    return await db_all("SELECT * FROM promocodes ORDER BY created_at DESC")


async def get_promo_by_code(code: str):
    return await db_one(
        "SELECT * FROM promocodes WHERE code=$1 AND is_active=1", (code.upper(),)
    )


async def get_promo_by_id(pid: int):
    return await db_one("SELECT * FROM promocodes WHERE id=$1", (pid,))


async def create_promo(code, promo_type, value, description, max_uses):
    return await db_insert(
        """INSERT INTO promocodes
           (code,promo_type,value,description,max_uses,created_at)
           VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",
        (code.upper(), promo_type, value, description, max_uses,
         datetime.now().isoformat()),
    )


async def delete_promo(promo_id: int):
    await db_run("UPDATE promocodes SET is_active=0 WHERE id=$1", (promo_id,))


async def check_promo_usage(user_id: int, promo_id: int) -> bool:
    r = await db_one(
        "SELECT id FROM promo_usage WHERE user_id=$1 AND promo_id=$2",
        (user_id, promo_id),
    )
    return r is not None


async def use_promo(user_id: int, promo_id: int, order_id: int = 0):
    try:
        await db_run(
            "INSERT INTO promo_usage(user_id,promo_id,order_id,used_at) VALUES($1,$2,$3,$4)",
            (user_id, promo_id, order_id, datetime.now().isoformat()),
        )
    except Exception:
        pass
    await db_run(
        "UPDATE promocodes SET used_count=used_count+1 WHERE id=$1", (promo_id,)
    )


def apply_promo_to_price(price: float, promo) -> tuple[float, float, str]:
    """Возвращает (итоговая_цена, скидка, описание)."""
    if not promo:
        return price, 0, ""
    pt  = promo["promo_type"]
    val = promo["value"]

    if pt == "discount_percent":
        disc = round(price * val / 100, 0)
        return max(price - disc, 0), disc, f"Скидка {int(val)}%: -{fmt_price(disc)}"
    elif pt == "discount_fixed":
        disc = min(val, price)
        return max(price - disc, 0), disc, f"Скидка: -{fmt_price(disc)}"
    elif pt == "cashback_bonus":
        return price, 0, f"Бонус {fmt_price(val)} на счёт после покупки"
    elif pt == "gift":
        return price, 0, f"🎁 Подарок: {promo['description']}"
    elif pt == "free_delivery":
        return price, 0, "🚚 Бесплатная доставка"
    elif pt == "special_offer":
        return price, 0, f"✨ {promo['description']}"
    return price, 0, ""


async def validate_promo(code: str, user_id: int) -> tuple:
    """Возвращает (promo | None, error_text)."""
    promo = await get_promo_by_code(code)
    if not promo:
        return None, "❌ Промокод не найден или неактивен."
    if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
        return None, "❌ Промокод исчерпал лимит использований."
    used = await check_promo_usage(user_id, promo["id"])
    if used:
        return None, "❌ Вы уже использовали этот промокод."
    return promo, ""
