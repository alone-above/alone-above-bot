"""
╔══════════════════════════════════════════════════════════╗
║  SHOPBOT — main.py                                       ║
║  Точка входа. Запуск: python main.py                     ║
╚══════════════════════════════════════════════════════════╝
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN, USD_KZT_RATE, CASHBACK_PERCENT,
    DATABASE_INTERNAL_URL, DATABASE_PUBLIC_URL,
)
from db import init_db, close_pool
from handlers import setup_routers
import uvicorn
from api import app


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\033[35m" + "═" * 58)
    print("  🛍  SHOPBOT — Шымкент, Казахстан")
    print("  🗄  PostgreSQL (asyncpg) + aiogram 3.x + FastAPI")
    print("═" * 58 + "\033[0m")
    print(f"  💱 Курс USD/KZT : {USD_KZT_RATE} (фикс.)")
    print(f"  🎁 Кэшбэк       : {CASHBACK_PERCENT}%")
    print(f"  🔌 DB internal  : {DATABASE_INTERNAL_URL}")
    print(f"  🌐 DB public    : {DATABASE_PUBLIC_URL}")
    print()

    # Инициализируем БД (пул создаётся здесь — с авто-фоллбэком)
    await init_db()

    bot     = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp      = Dispatcher(storage=storage)

    setup_routers(dp)

    # Настраиваем сервер FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    print("\033[32m  🚀 Бот и API запущены!\033[0m\n")

    try:
        # Запускаем бота и API одновременно
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            server.serve()
        )
    finally:
        await close_pool()
        await bot.session.close()
        print("\033[33m  🛑 Бот остановлен\033[0m")


if __name__ == "__main__":
    asyncio.run(main())
