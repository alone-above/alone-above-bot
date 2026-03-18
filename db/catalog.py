"""db/catalog.py — Категории и товары"""
import json
import random
import string
from datetime import datetime
from .pool import (
    db_one, db_all, db_run, db_insert,
    cached_db_one, cached_db_all, _cache_invalidate,
)


# ── Утилиты ────────────────────────────────────────────
def gen_short_id() -> str:
    return "".join(random.choices(string.digits, k=5))


def parse_sizes(product: dict) -> list:
    try:
        return json.loads(product["sizes"] or "[]")
    except Exception:
        return []


# ── Категории ──────────────────────────────────────────
async def get_categories(parent_id: int = 0) -> list:
    return await cached_db_all(
        f"categories:p{parent_id}",
        "SELECT * FROM categories WHERE parent_id=$1 ORDER BY id",
        (parent_id,),
    )


async def get_all_categories() -> list:
    return await cached_db_all(
        "categories:all", "SELECT * FROM categories ORDER BY id"
    )


async def get_category(cid: int):
    return await db_one("SELECT * FROM categories WHERE id=$1", (cid,))


async def add_category(name: str, parent_id: int = 0):
    await db_run(
        "INSERT INTO categories(name, parent_id) VALUES($1, $2)", (name, parent_id)
    )
    _cache_invalidate("categories")


async def del_category(cid: int):
    await db_run("UPDATE products SET is_active=0 WHERE category_id=$1", (cid,))
    await db_run(
        "DELETE FROM cart WHERE product_id IN (SELECT id FROM products WHERE category_id=$1)",
        (cid,),
    )
    await db_run(
        "DELETE FROM wishlist WHERE product_id IN (SELECT id FROM products WHERE category_id=$1)",
        (cid,),
    )
    subcats = await db_all("SELECT id FROM categories WHERE parent_id=$1", (cid,))
    for sc in subcats:
        sid = sc["id"]
        await db_run("UPDATE products SET is_active=0 WHERE category_id=$1", (sid,))
        await db_run(
            "DELETE FROM cart WHERE product_id IN (SELECT id FROM products WHERE category_id=$1)",
            (sid,),
        )
        await db_run(
            "DELETE FROM wishlist WHERE product_id IN (SELECT id FROM products WHERE category_id=$1)",
            (sid,),
        )
        await db_run("DELETE FROM categories WHERE id=$1", (sid,))
    await db_run("DELETE FROM categories WHERE id=$1", (cid,))
    _cache_invalidate("categories", "products")


# ── Товары ─────────────────────────────────────────────
async def get_products(cid: int) -> list:
    return await cached_db_all(
        f"products:{cid}",
        "SELECT * FROM products WHERE category_id=$1 AND is_active=1",
        (cid,),
    )


async def get_product(pid: int):
    return await cached_db_one(
        f"product:{pid}", "SELECT * FROM products WHERE id=$1", (pid,)
    )


async def add_product(
    cid, name, desc, price, sizes_list, stock,
    seller_username="", seller_phone="",
    card_file_id="", card_media_type="", gallery=None,
):
    sizes_json   = json.dumps(sizes_list, ensure_ascii=False)
    gallery_json = json.dumps(gallery or [], ensure_ascii=False)
    short_id     = gen_short_id()
    pid = await db_insert(
        """INSERT INTO products
           (category_id, name, description, price, sizes, stock,
            seller_username, seller_phone,
            card_file_id, card_media_type, gallery, is_active, short_id, created_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,1,$12,$13)
           RETURNING id""",
        (
            cid, name, desc, price, sizes_json, stock,
            seller_username, seller_phone,
            card_file_id, card_media_type, gallery_json,
            short_id, datetime.now().isoformat(),
        ),
    )
    _cache_invalidate("products", "categories")
    return pid


async def update_product_field(pid: int, field: str, value):
    allowed = {
        "name", "description", "price", "sizes", "stock",
        "seller_username", "seller_phone",
        "card_file_id", "card_media_type", "gallery",
    }
    if field not in allowed:
        return
    await db_run(f"UPDATE products SET {field}=$1 WHERE id=$2", (value, pid))
    _cache_invalidate(f"product:{pid}", "products")


async def del_product(pid: int):
    await db_run("UPDATE products SET is_active=0 WHERE id=$1", (pid,))
    await db_run("DELETE FROM cart WHERE product_id=$1", (pid,))
    await db_run("DELETE FROM wishlist WHERE product_id=$1", (pid,))
    _cache_invalidate("products", f"product:{pid}")


async def reduce_stock(pid: int):
    await db_run(
        "UPDATE products SET stock=GREATEST(0, stock-1) WHERE id=$1", (pid,)
    )
    _cache_invalidate(f"product:{pid}")
