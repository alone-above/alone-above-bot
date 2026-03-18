"""utils/fmt.py — Форматирование цен, дат, статусов"""
from datetime import datetime
from config import ORDER_STATUS_LABELS


def fmt_dt() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def fmt_price(kzt) -> str:
    try:
        return f"{int(float(kzt)):,}".replace(",", " ") + " ₸"
    except Exception:
        return f"{kzt} ₸"


def order_status_text(status: str) -> str:
    return ORDER_STATUS_LABELS.get(status, status)
