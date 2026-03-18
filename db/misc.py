"""db/misc.py — Отзывы, жалобы, реклама, медиа, настройки, статистика, лог"""
from datetime import datetime
from config import BOT_MSG_DEFAULTS, AD_PRICE_KZT
from .pool import db_one, db_all, db_run, db_insert, cached_db_one, _cache_invalidate


# ── Покупки ────────────────────────────────────────────
async def add_purchase(uid: int, pid: int, price: float, method: str = "crypto"):
    await db_run(
        "INSERT INTO purchases(user_id,product_id,price,method,purchased_at) VALUES($1,$2,$3,$4,$5)",
        (uid, pid, price, method, datetime.now().isoformat()),
    )
    await db_run(
        "UPDATE users SET total_purchases=total_purchases+1, total_spent=total_spent+$1 WHERE user_id=$2",
        (price, uid),
    )


# ── Лог событий ───────────────────────────────────────
async def log_event(event_type: str, user_id: int = 0, data: str = ""):
    await db_run(
        "INSERT INTO event_log(event_type,user_id,data,created_at) VALUES($1,$2,$3,$4)",
        (event_type, user_id, data, datetime.now().isoformat()),
    )


# ── Статистика ────────────────────────────────────────
async def get_stats() -> tuple:
    uc  = (await db_one("SELECT COUNT(*) AS c FROM users"))["c"]
    pc  = (await db_one("SELECT COUNT(*) AS c FROM purchases"))["c"]
    rv  = (await db_one("SELECT COALESCE(SUM(price),0) AS s FROM purchases"))["s"]
    ac  = (await db_one("SELECT COUNT(*) AS c FROM products WHERE is_active=1"))["c"]
    oc  = (await db_one(
        "SELECT COUNT(*) AS c FROM orders WHERE status NOT IN ('delivered','confirmed')"
    ))["c"]
    prc = (await db_one("SELECT COUNT(*) AS c FROM promocodes WHERE is_active=1"))["c"]
    bc  = (await db_one("SELECT COUNT(*) AS c FROM users WHERE is_banned=1"))["c"]
    cmp = (await db_one("SELECT COUNT(*) AS c FROM complaints WHERE status='open'"))["c"]
    return uc, pc, rv, ac, oc, prc, bc, cmp


# ── Медиа-настройки ───────────────────────────────────
async def set_media(key: str, mtype: str, fid: str):
    await db_run(
        """INSERT INTO media_settings(key,media_type,file_id) VALUES($1,$2,$3)
           ON CONFLICT(key) DO UPDATE SET media_type=$2, file_id=$3""",
        (key, mtype, fid),
    )
    _cache_invalidate(f"media:{key}")


async def get_media(key: str):
    return await cached_db_one(
        f"media:{key}", "SELECT * FROM media_settings WHERE key=$1", (key,)
    )


# ── Настройки магазина ────────────────────────────────
async def set_setting(k: str, v: str):
    await db_run(
        "INSERT INTO shop_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=$2",
        (k, v),
    )
    _cache_invalidate(f"setting:{k}")


async def get_setting(k: str, default: str = "") -> str:
    r = await cached_db_one(
        f"setting:{k}", "SELECT value FROM shop_settings WHERE key=$1", (k,)
    )
    return r["value"] if r else default


# ── Сообщения бота ────────────────────────────────────
async def get_bot_msg(key: str) -> str:
    r = await db_one("SELECT text FROM bot_messages WHERE key=$1", (key,))
    if r and r["text"]:
        return r["text"]
    return BOT_MSG_DEFAULTS.get(key, key)


async def set_bot_msg(key: str, text: str, media_type: str = "", file_id: str = ""):
    await db_run(
        """INSERT INTO bot_messages(key, text, media_type, file_id) VALUES($1,$2,$3,$4)
           ON CONFLICT(key) DO UPDATE SET text=$2, media_type=$3, file_id=$4""",
        (key, text, media_type, file_id),
    )
    _cache_invalidate(f"botmsg:{key}")


async def get_bot_msg_media(key: str):
    return await db_one("SELECT * FROM bot_messages WHERE key=$1", (key,))


# ── Отзывы ────────────────────────────────────────────
async def add_review(uid: int, pid: int, oid: int, rating: int, comment: str):
    await db_run(
        "INSERT INTO reviews(user_id,product_id,order_id,rating,comment,created_at) VALUES($1,$2,$3,$4,$5,$6)",
        (uid, pid, oid, rating, comment, datetime.now().isoformat()),
    )


async def get_reviews(pid: int, limit: int = 10) -> list:
    return await db_all(
        "SELECT * FROM reviews WHERE product_id=$1 ORDER BY created_at DESC LIMIT $2",
        (pid, limit),
    )


async def get_avg_rating(pid: int) -> float:
    r = await db_one("SELECT AVG(rating) AS avg FROM reviews WHERE product_id=$1", (pid,))
    return round(float(r["avg"]), 1) if r and r["avg"] else 0.0


async def get_review_count(pid: int) -> int:
    r = await db_one("SELECT COUNT(*) AS cnt FROM reviews WHERE product_id=$1", (pid,))
    return r["cnt"] if r else 0


# ── Жалобы ────────────────────────────────────────────
async def create_complaint(uid: int, order_id: int, description: str) -> int:
    return await db_insert(
        """INSERT INTO complaints(user_id,order_id,description,created_at)
           VALUES($1,$2,$3,$4) RETURNING id""",
        (uid, order_id, description, datetime.now().isoformat()),
    )


# ── Реклама ───────────────────────────────────────────
async def create_ad_request(uid: int, description: str, method: str):
    return await db_insert(
        """INSERT INTO ad_requests(user_id,description,method,amount,created_at)
           VALUES($1,$2,$3,$4,$5) RETURNING id""",
        (uid, description, method, AD_PRICE_KZT, datetime.now().isoformat()),
    )


async def get_ad_request(aid: int):
    return await db_one("SELECT * FROM ad_requests WHERE id=$1", (aid,))


async def set_ad_status(aid: int, status: str):
    await db_run("UPDATE ad_requests SET status=$1 WHERE id=$2", (status, aid))
