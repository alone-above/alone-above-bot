"""
db/init.py — Инициализация и миграции PostgreSQL
"""
import logging
from .pool import get_pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         BIGINT PRIMARY KEY,
            username        TEXT DEFAULT '',
            first_name      TEXT DEFAULT '',
            phone           TEXT DEFAULT '',
            default_address TEXT DEFAULT '',
            total_purchases INTEGER DEFAULT 0,
            total_spent     REAL DEFAULT 0,
            bonus_balance   REAL DEFAULT 0,
            registered_at   TEXT,
            agreed_terms    INTEGER DEFAULT 0,
            is_banned       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS categories (
            id        SERIAL PRIMARY KEY,
            name      TEXT NOT NULL,
            parent_id INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
            id              SERIAL PRIMARY KEY,
            category_id     INTEGER,
            name            TEXT NOT NULL,
            description     TEXT DEFAULT '',
            price           REAL NOT NULL,
            sizes           TEXT DEFAULT '[]',
            stock           INTEGER DEFAULT 0,
            seller_username TEXT DEFAULT '',
            seller_phone    TEXT DEFAULT '',
            card_file_id    TEXT DEFAULT '',
            card_media_type TEXT DEFAULT '',
            gallery         TEXT DEFAULT '[]',
            is_active       INTEGER DEFAULT 1,
            short_id        TEXT DEFAULT '',
            created_at      TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT,
            username    TEXT DEFAULT '',
            first_name  TEXT DEFAULT '',
            product_id  INTEGER,
            size        TEXT DEFAULT '',
            price       REAL,
            method      TEXT DEFAULT 'crypto',
            phone       TEXT DEFAULT '',
            address     TEXT DEFAULT '',
            promo_code  TEXT DEFAULT '',
            discount    REAL DEFAULT 0,
            status      TEXT DEFAULT 'processing',
            note        TEXT DEFAULT '',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS order_history (
            id         SERIAL PRIMARY KEY,
            order_id   INTEGER,
            status     TEXT,
            changed_by BIGINT DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS order_notes (
            id         SERIAL PRIMARY KEY,
            order_id   INTEGER UNIQUE,
            note       TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS purchases (
            id           SERIAL PRIMARY KEY,
            user_id      BIGINT,
            product_id   INTEGER,
            price        REAL,
            method       TEXT DEFAULT 'crypto',
            purchased_at TEXT
        );
        CREATE TABLE IF NOT EXISTS media_settings (
            key        TEXT PRIMARY KEY,
            media_type TEXT,
            file_id    TEXT
        );
        CREATE TABLE IF NOT EXISTS shop_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS crypto_payments (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT,
            product_id  INTEGER,
            size        TEXT DEFAULT '',
            invoice_id  TEXT UNIQUE,
            amount_kzt  REAL,
            amount_usd  REAL,
            promo_code  TEXT DEFAULT '',
            discount    REAL DEFAULT 0,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS kaspi_payments (
            id             SERIAL PRIMARY KEY,
            user_id        BIGINT,
            product_id     INTEGER,
            size           TEXT DEFAULT '',
            amount         REAL,
            promo_code     TEXT DEFAULT '',
            discount       REAL DEFAULT 0,
            buyer_note     TEXT DEFAULT '',
            status         TEXT DEFAULT 'pending',
            manager_msg_id BIGINT DEFAULT 0,
            created_at     TEXT
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT,
            product_id  INTEGER,
            order_id    INTEGER,
            rating      INTEGER,
            comment     TEXT,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS ad_requests (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT,
            description TEXT,
            method      TEXT DEFAULT 'crypto',
            amount      REAL DEFAULT 500,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS promocodes (
            id          SERIAL PRIMARY KEY,
            code        TEXT UNIQUE NOT NULL,
            promo_type  TEXT NOT NULL,
            value       REAL DEFAULT 0,
            description TEXT DEFAULT '',
            max_uses    INTEGER DEFAULT 0,
            used_count  INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS promo_usage (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT,
            promo_id   INTEGER,
            order_id   INTEGER DEFAULT 0,
            used_at    TEXT,
            UNIQUE(user_id, promo_id)
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT,
            order_id    INTEGER DEFAULT 0,
            description TEXT,
            status      TEXT DEFAULT 'open',
            file_id     TEXT DEFAULT '',
            file_type   TEXT DEFAULT '',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS event_log (
            id         SERIAL PRIMARY KEY,
            event_type TEXT,
            user_id    BIGINT DEFAULT 0,
            data       TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id    BIGINT PRIMARY KEY,
            role       TEXT DEFAULT 'buyer',
            granted_by BIGINT DEFAULT 0,
            granted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS partners (
            user_id       BIGINT PRIMARY KEY,
            ref_code      TEXT UNIQUE NOT NULL,
            bonus_new     TEXT DEFAULT '{"type":"percent","value":5}',
            bonus_repeat  TEXT DEFAULT '{"type":"percent","value":3}',
            total_invited INTEGER DEFAULT 0,
            total_earned  REAL DEFAULT 0,
            created_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS partner_referrals (
            id           SERIAL PRIMARY KEY,
            partner_id   BIGINT,
            referred_uid BIGINT,
            is_new_buyer INTEGER DEFAULT 1,
            bonus_amount REAL DEFAULT 0,
            order_id     INTEGER DEFAULT 0,
            created_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS drops (
            id              SERIAL PRIMARY KEY,
            category_id     INTEGER,
            name            TEXT NOT NULL,
            description     TEXT DEFAULT '',
            price           REAL NOT NULL,
            sizes           TEXT DEFAULT '[]',
            stock           INTEGER DEFAULT 0,
            start_at        TEXT NOT NULL,
            card_file_id    TEXT DEFAULT '',
            card_media_type TEXT DEFAULT '',
            gallery         TEXT DEFAULT '[]',
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT
        );
        CREATE TABLE IF NOT EXISTS bot_messages (
            key        TEXT PRIMARY KEY,
            text       TEXT,
            media_type TEXT DEFAULT '',
            file_id    TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS cart (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            product_id INTEGER NOT NULL,
            size       TEXT DEFAULT 'ONE_SIZE',
            added_at   TEXT,
            UNIQUE(user_id, product_id, size)
        );
        CREATE TABLE IF NOT EXISTS wishlist (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            product_id INTEGER NOT NULL,
            added_at   TEXT,
            UNIQUE(user_id, product_id)
        );
        """)

        # Миграции — добавить колонки если не существуют
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code TEXT DEFAULT ''",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS short_id TEXT DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS note TEXT DEFAULT ''",
            "ALTER TABLE categories ADD COLUMN IF NOT EXISTS parent_id INTEGER DEFAULT 0",
            "ALTER TABLE kaspi_payments ADD COLUMN IF NOT EXISTS buyer_note TEXT DEFAULT ''",
            "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS file_id TEXT DEFAULT ''",
            "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT ''",
        ]
        for sql in migrations:
            try:
                await conn.execute(sql)
            except Exception:
                pass

    logging.info("✅ PostgreSQL БД инициализирована")
