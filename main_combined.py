import asyncio
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from db import init_db, close_pool
from handlers import setup_routers
from api import app as fastapi_app

async def run_bot():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    setup_routers(dp)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

async def main():
    await init_db()
    
    # Запускаем FastAPI в фоне
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Запускаем бота и сервер параллельно
    await asyncio.gather(
        server.serve(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

И `Procfile`:
```
web: python main_combined.py
