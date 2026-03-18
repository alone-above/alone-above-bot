"""db/payments.py — CryptoBot, Kaspi и курс валют"""
import ssl
import aiohttp
from datetime import datetime
from config import CRYPTOBOT_TOKEN, USD_KZT_RATE
from .pool import db_one, db_run, db_insert


# ── SSL-контекст (Railway / другие хостинги) ──────────
def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx


# ── Курс USD/KZT ──────────────────────────────────────
async def get_usd_kzt_rate() -> float:
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=_ssl_ctx())
        ) as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
                return float(data["rates"]["KZT"])
    except Exception:
        return USD_KZT_RATE


def kzt_to_usd(kzt: float, rate: float) -> float:
    return round(kzt / rate, 2)


# ── CryptoBot ─────────────────────────────────────────
async def create_invoice(amount_usd: float, desc: str, payload: str, bot_username: str = ""):
    url = "https://pay.crypt.bot/api/createInvoice"
    hdr = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": desc,
        "payload": payload,
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/{bot_username}" if bot_username else "https://t.me/",
    }
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=_ssl_ctx())
    ) as s:
        async with s.post(url, headers=hdr, json=data) as r:
            res = await r.json()
            return res["result"] if res.get("ok") else None


async def check_invoice(inv_id: str):
    url = "https://pay.crypt.bot/api/getInvoices"
    hdr = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=_ssl_ctx())
    ) as s:
        async with s.get(url, headers=hdr, params={"invoice_ids": inv_id}) as r:
            res = await r.json()
            if res.get("ok") and res["result"]["items"]:
                return res["result"]["items"][0]
            return None


# ── Crypto-платежи (таблица) ──────────────────────────
async def save_crypto(uid, pid, size, inv_id, amount_kzt, amount_usd,
                      promo_code="", discount=0):
    try:
        await db_run(
            """INSERT INTO crypto_payments
               (user_id,product_id,size,invoice_id,amount_kzt,amount_usd,
                promo_code,discount,created_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            (uid, pid, size, inv_id, amount_kzt, amount_usd,
             promo_code, discount, datetime.now().isoformat()),
        )
    except Exception:
        pass


async def get_crypto(inv_id: str):
    return await db_one("SELECT * FROM crypto_payments WHERE invoice_id=$1", (inv_id,))


async def set_crypto_paid(inv_id: str):
    await db_run(
        "UPDATE crypto_payments SET status='paid' WHERE invoice_id=$1", (inv_id,)
    )


# ── Kaspi-платежи (таблица) ───────────────────────────
async def save_kaspi(uid, pid, size, amount, promo_code="", discount=0, buyer_note=""):
    return await db_insert(
        """INSERT INTO kaspi_payments
           (user_id,product_id,size,amount,promo_code,discount,buyer_note,created_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
        (uid, pid, size, amount, promo_code, discount, buyer_note,
         datetime.now().isoformat()),
    )


async def get_kaspi(kid: int):
    return await db_one("SELECT * FROM kaspi_payments WHERE id=$1", (kid,))


async def set_kaspi_status(kid: int, status: str, mgr_mid=None):
    if mgr_mid is not None:
        await db_run(
            "UPDATE kaspi_payments SET status=$1, manager_msg_id=$2 WHERE id=$3",
            (status, mgr_mid, kid),
        )
    else:
        await db_run("UPDATE kaspi_payments SET status=$1 WHERE id=$2", (status, kid))
