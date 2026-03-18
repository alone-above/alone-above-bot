"""
╔══════════════════════════════════════════════════════╗
║  db/pool.py — asyncpg пул и базовые хелперы          ║
║                                                      ║
║  Стратегия подключения:                               ║
║  1. Пробуем internal URL (Railway internal network)   ║
║  2. Если не доступен — фоллбэк на публичный URL       ║
╚══════════════════════════════════════════════════════╝
"""
import logging
import time as _time
import asyncpg
from config import DATABASE_INTERNAL_URL, DATABASE_PUBLIC_URL

log = logging.getLogger(__name__)

# ── Пул соединений ─────────────────────────────────────
_pool: asyncpg.Pool | None = None


async def _try_create_pool(url: str, label: str) -> asyncpg.Pool | None:
    """Попытаться создать пул с данным URL. Возвращает None при ошибке."""
    try:
        pool = await asyncpg.create_pool(
            url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            # Таймаут соединения — важно для быстрого фоллбэка
            timeout=5,
        )
        # Проверяем что соединение реально работает
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        log.info(f"✅ PostgreSQL подключён через {label}")
        return pool
    except Exception as e:
        log.warning(f"⚠️  {label} недоступен: {e}")
        return None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    # Шаг 1 — пробуем внутренний Railway URL
    _pool = await _try_create_pool(DATABASE_INTERNAL_URL, "internal (railway.internal)")

    # Шаг 2 — если не получилось, пробуем публичный URL
    if _pool is None:
        log.info("🔄 Переключаемся на публичный URL...")
        _pool = await _try_create_pool(DATABASE_PUBLIC_URL, "public (rlwy.net)")

    if _pool is None:
        raise ConnectionError(
            "❌ Не удалось подключиться к PostgreSQL ни через internal, ни через public URL.\n"
            f"  Internal: {DATABASE_INTERNAL_URL}\n"
            f"  Public:   {DATABASE_PUBLIC_URL}"
        )

    return _pool


async def close_pool():
    """Закрыть пул при завершении бота."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        log.info("🔌 PostgreSQL пул закрыт")


# ── Лёгкий in-memory кэш (TTL = 8 сек) ───────────────
_CACHE: dict = {}
CACHE_TTL    = 8


def _cache_get(key: str):
    entry = _CACHE.get(key)
    if entry and _time.monotonic() < entry[1]:
        return entry[0], True
    return None, False


def _cache_set(key: str, value):
    _CACHE[key] = (value, _time.monotonic() + CACHE_TTL)
    return value


def _cache_invalidate(*prefixes: str):
    dead = [k for k in _CACHE for p in prefixes
            if k == p or k.startswith(p + ":")]
    for k in dead:
        _CACHE.pop(k, None)


# ── Обёртки asyncpg ────────────────────────────────────
async def db_one(sql: str, params=()):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)
        return dict(row) if row else None


async def db_all(sql: str, params=()):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]


async def db_run(sql: str, params=()):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql, *params)


async def db_insert(sql: str, params=()):
    """INSERT … RETURNING id → возвращает id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)
        return row["id"] if row else None


# ── Кешированные запросы ───────────────────────────────
async def cached_db_one(cache_key: str, sql: str, params=()):
    v, hit = _cache_get(cache_key)
    if hit:
        return v
    v = await db_one(sql, params)
    return _cache_set(cache_key, v)


async def cached_db_all(cache_key: str, sql: str, params=()):
    v, hit = _cache_get(cache_key)
    if hit:
        return v
    v = await db_all(sql, params)
    return _cache_set(cache_key, v)

