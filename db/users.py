"""db/users.py — CRUD для таблицы users"""
from datetime import datetime
from config import CASHBACK_PERCENT
from .pool import db_run, db_all, cached_db_one, _cache_invalidate


async def ensure_user(u):
    await db_run(
        """INSERT INTO users(user_id, username, first_name, registered_at)
           VALUES($1, $2, $3, $4)
           ON CONFLICT(user_id) DO UPDATE SET username=$2, first_name=$3""",
        (u.id, u.username or "", u.first_name or "", datetime.now().isoformat()),
    )
    _cache_invalidate(f"user:{u.id}")


async def get_user(uid: int):
    return await cached_db_one(
        f"user:{uid}", "SELECT * FROM users WHERE user_id=$1", (uid,)
    )


async def set_agreed_terms(uid: int):
    await db_run("UPDATE users SET agreed_terms=1 WHERE user_id=$1", (uid,))
    _cache_invalidate(f"user:{uid}")


async def has_agreed_terms(uid: int) -> bool:
    u = await get_user(uid)
    return bool(u and u.get("agreed_terms", 0))


async def update_user_phone(uid: int, phone: str):
    await db_run("UPDATE users SET phone=$1 WHERE user_id=$2", (phone, uid))
    _cache_invalidate(f"user:{uid}")


async def update_user_address(uid: int, address: str):
    await db_run("UPDATE users SET default_address=$1 WHERE user_id=$2", (address, uid))
    _cache_invalidate(f"user:{uid}")


async def add_bonus(uid: int, amount_kzt: float) -> float:
    bonus = round(amount_kzt * CASHBACK_PERCENT / 100, 0)
    await db_run(
        "UPDATE users SET bonus_balance=bonus_balance+$1 WHERE user_id=$2", (bonus, uid)
    )
    _cache_invalidate(f"user:{uid}")
    return bonus


async def ban_user(uid: int):
    await db_run("UPDATE users SET is_banned=1 WHERE user_id=$1", (uid,))
    _cache_invalidate(f"user:{uid}")


async def unban_user(uid: int):
    await db_run("UPDATE users SET is_banned=0 WHERE user_id=$1", (uid,))
    _cache_invalidate(f"user:{uid}")


async def is_banned(uid: int) -> bool:
    u = await get_user(uid)
    return bool(u and u.get("is_banned", 0))


async def all_user_ids() -> list[int]:
    rows = await db_all("SELECT user_id FROM users WHERE is_banned=0")
    return [r["user_id"] for r in rows]


async def get_all_users(limit: int = 50, offset: int = 0) -> list:
    return await db_all(
        "SELECT * FROM users ORDER BY registered_at DESC LIMIT $1 OFFSET $2",
        (limit, offset),
    )
