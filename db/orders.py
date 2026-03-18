"""db/orders.py — Заказы"""
from datetime import datetime
from .pool import db_one, db_all, db_run, db_insert


async def create_order(
    uid, username, first_name, pid, size, price,
    method, phone="", address="", promo_code="", discount=0,
):
    oid = await db_insert(
        """INSERT INTO orders
           (user_id, username, first_name, product_id, size, price,
            method, phone, address, promo_code, discount, status, created_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'processing',$12)
           RETURNING id""",
        (
            uid, username or "", first_name or "", pid, size, price,
            method, phone, address, promo_code, discount,
            datetime.now().isoformat(),
        ),
    )
    if oid:
        await db_run(
            "INSERT INTO order_history(order_id, status, changed_by, created_at) VALUES($1,$2,$3,$4)",
            (oid, "processing", uid, datetime.now().isoformat()),
        )
    return oid


async def get_order(oid: int):
    return await db_one("SELECT * FROM orders WHERE id=$1", (oid,))


async def set_order_status(oid: int, status: str, changed_by: int = 0):
    await db_run("UPDATE orders SET status=$1 WHERE id=$2", (status, oid))
    await db_run(
        "INSERT INTO order_history(order_id, status, changed_by, created_at) VALUES($1,$2,$3,$4)",
        (oid, status, changed_by, datetime.now().isoformat()),
    )


async def get_user_orders(uid: int) -> list:
    return await db_all(
        """SELECT o.*, p.name AS pname
           FROM orders o JOIN products p ON o.product_id=p.id
           WHERE o.user_id=$1 ORDER BY o.created_at DESC LIMIT 10""",
        (uid,),
    )


async def get_order_history(oid: int) -> list:
    return await db_all(
        "SELECT * FROM order_history WHERE order_id=$1 ORDER BY created_at ASC",
        (oid,),
    )


async def set_order_note(oid: int, note: str):
    await db_run(
        """INSERT INTO order_notes(order_id, note, created_at) VALUES($1,$2,$3)
           ON CONFLICT(order_id) DO UPDATE SET note=$2""",
        (oid, note, datetime.now().isoformat()),
    )


async def get_order_note(oid: int) -> str:
    r = await db_one("SELECT note FROM order_notes WHERE order_id=$1", (oid,))
    return r["note"] if r else ""
