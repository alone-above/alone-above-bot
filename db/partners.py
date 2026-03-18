"""db/partners.py — Партнёрская программа"""
import json
from datetime import datetime
from .pool import db_one, db_all, db_run, _cache_invalidate
from .roles import set_user_role


async def get_partner(uid: int):
    return await db_one("SELECT * FROM partners WHERE user_id=$1", (uid,))


async def create_partner(uid: int, ref_code: str) -> bool:
    existing = await db_one(
        "SELECT user_id FROM partners WHERE ref_code=$1", (ref_code,)
    )
    if existing:
        return False
    await db_run(
        """INSERT INTO partners(user_id, ref_code, created_at)
           VALUES($1,$2,$3) ON CONFLICT(user_id) DO NOTHING""",
        (uid, ref_code.upper(), datetime.now().isoformat()),
    )
    await set_user_role(uid, "partner")
    return True


async def update_partner_bonuses(uid: int, bonus_new: dict, bonus_repeat: dict):
    await db_run(
        "UPDATE partners SET bonus_new=$1, bonus_repeat=$2 WHERE user_id=$3",
        (json.dumps(bonus_new), json.dumps(bonus_repeat), uid),
    )


async def get_partner_by_ref(ref_code: str):
    return await db_one(
        "SELECT * FROM partners WHERE ref_code=$1", (ref_code.upper(),)
    )


async def record_partner_referral(
    partner_id: int, referred_uid: int,
    is_new: bool, bonus: float, order_id: int = 0,
):
    await db_run(
        """INSERT INTO partner_referrals
           (partner_id, referred_uid, is_new_buyer, bonus_amount, order_id, created_at)
           VALUES($1,$2,$3,$4,$5,$6)""",
        (partner_id, referred_uid, 1 if is_new else 0, bonus, order_id,
         datetime.now().isoformat()),
    )
    await db_run(
        """UPDATE partners
           SET total_invited=total_invited+1, total_earned=total_earned+$1
           WHERE user_id=$2""",
        (bonus, partner_id),
    )
    await db_run(
        "UPDATE users SET bonus_balance=bonus_balance+$1 WHERE user_id=$2",
        (bonus, partner_id),
    )
    _cache_invalidate(f"user:{partner_id}")


async def get_partner_referrals(partner_id: int, limit: int = 20) -> list:
    return await db_all(
        """SELECT pr.*, u.username, u.first_name
           FROM partner_referrals pr
           LEFT JOIN users u ON pr.referred_uid=u.user_id
           WHERE pr.partner_id=$1 ORDER BY pr.created_at DESC LIMIT $2""",
        (partner_id, limit),
    )


def calc_partner_bonus(price: float, bonus_cfg: dict) -> float:
    btype = bonus_cfg.get("type", "percent")
    val   = float(bonus_cfg.get("value", 0))
    if btype == "percent":
        return round(price * val / 100, 0)
    elif btype == "fixed":
        return round(val, 0)
    return 0.0
