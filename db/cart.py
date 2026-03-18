"""db/cart.py — Корзина и избранное"""
from datetime import datetime
from .pool import db_one, db_all, db_run


# ── Корзина ────────────────────────────────────────────
async def cart_add(uid: int, pid: int, size: str) -> bool:
    try:
        await db_run(
            """INSERT INTO cart(user_id,product_id,size,added_at)
               VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING""",
            (uid, pid, size, datetime.now().isoformat()),
        )
        return True
    except Exception:
        return False


async def cart_remove(uid: int, pid: int, size: str):
    await db_run(
        "DELETE FROM cart WHERE user_id=$1 AND product_id=$2 AND size=$3",
        (uid, pid, size),
    )


async def cart_get(uid: int) -> list:
    return await db_all(
        """SELECT c.id, c.product_id, c.size, c.added_at,
                  p.name, p.price, p.stock, p.card_file_id, p.card_media_type, p.is_active
           FROM cart c
           JOIN products p ON p.id = c.product_id
           WHERE c.user_id=$1
           ORDER BY c.added_at DESC""",
        (uid,),
    )


async def cart_clear(uid: int):
    await db_run("DELETE FROM cart WHERE user_id=$1", (uid,))


async def cart_count(uid: int) -> int:
    r = await db_one("SELECT COUNT(*) AS cnt FROM cart WHERE user_id=$1", (uid,))
    return r["cnt"] if r else 0


async def cart_has(uid: int, pid: int, size: str) -> bool:
    r = await db_one(
        "SELECT 1 FROM cart WHERE user_id=$1 AND product_id=$2 AND size=$3",
        (uid, pid, size),
    )
    return bool(r)


# ── Избранное ──────────────────────────────────────────
async def wish_add(uid: int, pid: int) -> bool:
    try:
        await db_run(
            """INSERT INTO wishlist(user_id,product_id,added_at)
               VALUES($1,$2,$3) ON CONFLICT DO NOTHING""",
            (uid, pid, datetime.now().isoformat()),
        )
        return True
    except Exception:
        return False


async def wish_remove(uid: int, pid: int):
    await db_run(
        "DELETE FROM wishlist WHERE user_id=$1 AND product_id=$2", (uid, pid)
    )


async def wish_get(uid: int) -> list:
    return await db_all(
        """SELECT w.product_id, w.added_at,
                  p.name, p.price, p.stock, p.card_file_id, p.card_media_type, p.is_active
           FROM wishlist w
           JOIN products p ON p.id = w.product_id
           WHERE w.user_id=$1
           ORDER BY w.added_at DESC""",
        (uid,),
    )


async def wish_has(uid: int, pid: int) -> bool:
    r = await db_one(
        "SELECT 1 FROM wishlist WHERE user_id=$1 AND product_id=$2", (uid, pid)
    )
    return bool(r)


async def wish_count(uid: int) -> int:
    r = await db_one(
        "SELECT COUNT(*) AS cnt FROM wishlist WHERE user_id=$1", (uid,)
    )
    return r["cnt"] if r else 0
