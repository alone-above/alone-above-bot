"""db/drops.py — Дропы"""
import json
from datetime import datetime
from .pool import db_all, db_run, db_insert


async def get_active_drops() -> list:
    now = datetime.now().isoformat()
    return await db_all(
        "SELECT * FROM drops WHERE is_active=1 AND start_at <= $1 ORDER BY start_at DESC",
        (now,),
    )


async def get_upcoming_drops() -> list:
    now = datetime.now().isoformat()
    return await db_all(
        "SELECT * FROM drops WHERE is_active=1 AND start_at > $1 ORDER BY start_at ASC",
        (now,),
    )


async def get_all_drops_admin() -> list:
    return await db_all("SELECT * FROM drops ORDER BY created_at DESC")


async def add_drop(
    cid, name, desc, price, sizes_list, stock, start_at,
    card_file_id="", card_media_type="", gallery=None,
):
    sizes_json   = json.dumps(sizes_list, ensure_ascii=False)
    gallery_json = json.dumps(gallery or [], ensure_ascii=False)
    return await db_insert(
        """INSERT INTO drops
           (category_id, name, description, price, sizes, stock, start_at,
            card_file_id, card_media_type, gallery, is_active, created_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1,$11) RETURNING id""",
        (
            cid, name, desc, price, sizes_json, stock, start_at,
            card_file_id, card_media_type, gallery_json,
            datetime.now().isoformat(),
        ),
    )


async def del_drop(did: int):
    await db_run("UPDATE drops SET is_active=0 WHERE id=$1", (did,))
