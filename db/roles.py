"""db/roles.py — Роли пользователей"""
from datetime import datetime
from config import ADMIN_IDS
from .pool import db_one, db_all, db_run, _cache_invalidate


async def get_user_role(uid: int) -> str:
    if uid in ADMIN_IDS:
        return "owner"
    r = await db_one("SELECT role FROM user_roles WHERE user_id=$1", (uid,))
    return r["role"] if r else "buyer"


async def set_user_role(uid: int, role: str, granted_by: int = 0):
    await db_run(
        """INSERT INTO user_roles(user_id, role, granted_by, granted_at)
           VALUES($1,$2,$3,$4)
           ON CONFLICT(user_id) DO UPDATE SET role=$2, granted_by=$3, granted_at=$4""",
        (uid, role, granted_by, datetime.now().isoformat()),
    )
    _cache_invalidate(f"user:{uid}")


async def get_users_by_role(role: str) -> list:
    return await db_all(
        """SELECT u.*, ur.role FROM users u
           JOIN user_roles ur ON u.user_id=ur.user_id
           WHERE ur.role=$1 ORDER BY ur.granted_at DESC""",
        (role,),
    )
