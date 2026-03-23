"""
api.py — FastAPI для мини-аппа
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from datetime import datetime

from db.catalog import get_categories, get_products, get_product
from db.cart import cart_get, wish_get
from db.users import get_user
from db.orders import create_order
from config import SHOP_NAME, SUPPORT_USERNAME, KASPI_PHONE, MANAGER_ID
from aiogram import Bot
from db.pool import db_run
from datetime import datetime

app = FastAPI(title="ShopBot API", description="API для мини-аппа магазина")

# Инициализируем бота для отправки уведомлений менеджеру
from config import BOT_TOKEN
bot_instance = Bot(token=BOT_TOKEN)

# CORS для веб-приложения
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    return {"status": "API is running", "message": "✅ API работает!"}

# Debug info
@app.get("/debug")
async def debug_info():
    try:
        cats = await get_categories()
        cat_count = len(cats) if cats else 0
        cat_names = [c.get('name', 'N/A') for c in (cats or [])][:5]
        
        return {
            "api_status": "✅ Работает",
            "categories_count": cat_count,
            "categories_sample": cat_names,
            "message": "API и БД инициализированы"
        }
    except Exception as e:
        return {
            "api_status": "❌ Ошибка",
            "error": str(e),
            "message": "Проблема с подключением к БД"
        }

# Тестовые эндпоинты (без параметров)
@app.get("/test/categories")
async def test_categories():
    """Тестовый эндпоинт для проверки категорий"""
    try:
        cats = await get_categories()
        return {
            "success": True,
            "count": len(cats) if cats else 0,
            "data": cats[:5] if cats else []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/test/products")
async def test_products():
    """Тестовый эндпоинт для проверки товаров"""
    try:
        if not await get_categories():
            return {"success": False, "error": "Нет категорий"}
        
        cat = (await get_categories())[0]
        prods = await get_products(cat['id'])
        return {
            "success": True,
            "category": cat['name'],
            "count": len(prods) if prods else 0,
            "data": prods[:3] if prods else []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# Категории
@app.get("/categories")
async def get_all_categories():
    try:
        categories = await get_categories()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/categories/{category_id}/products")
async def get_products_in_category(category_id: int):
    try:
        products = await get_products(category_id)
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Товары
@app.get("/products/{product_id}")
async def get_single_product(product_id: int):
    try:
        product = await get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"product": product}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Корзина
@app.get("/cart/{user_id}")
async def get_user_cart(user_id: int):
    try:
        cart = await cart_get(user_id)
        return {"cart": cart}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Избранное
@app.get("/wishlist/{user_id}")
async def get_user_wishlist(user_id: int):
    try:
        wishlist = await wish_get(user_id)
        return {"wishlist": wishlist}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Профиль
@app.get("/profile/{user_id}")
async def get_user_profile(user_id: int):
    try:
        user = await get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"profile": user}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# О магазине
@app.get("/store")
async def get_store_info():
    return {
        "name": SHOP_NAME,
        "support_username": SUPPORT_USERNAME,
        "kaspi_phone": KASPI_PHONE,
        "manager_id": MANAGER_ID
    }

# Поддержка
@app.get("/support")
async def get_support_info():
    return {
        "username": SUPPORT_USERNAME,
        "phone": KASPI_PHONE
    }

# ══════════════════════════════════════════════
# ЗАКАЗЫ
# ══════════════════════════════════════════════

class OrderItem(BaseModel):
    product_id: int
    size: str

class OrderRequest(BaseModel):
    items: list[OrderItem]
    phone: str
    address: str
    promo_code: str = ""
    method: str = "kaspi"
    user_id: int = None  # Реальный Telegram user ID

@app.post("/order/create")
async def create_order_handler(order: OrderRequest):
    """
    Создание заказа из корзины и отправка уведомления менеджеру с inline кнопками
    """
    try:
        if not order.items:
            return {"success": False, "error": "Корзина пуста"}
        
        # Используем реальный user_id из Telegram или fallback
        user_id = order.user_id or 999999
        
        # Для простоты берём первый товар из корзины
        first_item = order.items[0]
        product = await get_product(first_item.product_id)
        
        if not product:
            return {"success": False, "error": "Товар не найден"}
        
        user = await get_user(user_id)
        
        # Создаём пользователя если не существует
        if not user:
            await db_run(
                """INSERT INTO users(user_id, username, first_name, registered_at)
                   VALUES($1, $2, $3, $4)
                   ON CONFLICT(user_id) DO UPDATE SET username=$2, first_name=$3""",
                (user_id, "webappuser", "WebApp User", datetime.now().isoformat()),
            )
        
        price = product.get("price", 0)
        discount = 0
        
        # Создаём заказ
        order_id = await create_order(
            uid=user_id,
            username="webappuser",
            first_name="WebApp",
            pid=first_item.product_id,
            size=first_item.size,
            price=price,
            method=order.method,
            phone=order.phone,
            address=order.address,
            promo_code=order.promo_code,
            discount=discount,
        )
        
        if not order_id:
            return {
                "success": False,
                "error": "Ошибка при создании заказа"
            }
        
        # Формируем уведомление менеджеру с inline кнопками
        pname = product.get("name", "Товар")
        notif = (
            f"🔔 <b>Новый заказ #{order_id} (WebApp Kaspi)</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📦 <b>Товар:</b> {pname} ({first_item.size})\n"
            f"💰 <b>Сумма:</b> {price} ₸\n"
            f"📞 <b>Телефон:</b> {order.phone}\n"
            f"📍 <b>Адрес:</b> {order.address}\n\n"
            f"<blockquote>⏳ Ожидается оплата через Kaspi</blockquote>"
        )
        
        # Создаём inline кнопки для менеджера
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        manager_buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"weborder_confirm_{order_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"weborder_reject_{order_id}"),
                ]
            ]
        )
        
        # Отправляем уведомление менеджеру
        try:
            await bot_instance.send_message(
                MANAGER_ID, 
                notif, 
                parse_mode="HTML",
                reply_markup=manager_buttons
            )
            print(f"✅ Уведомление отправлено менеджеру (заказ #{order_id})")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления менеджеру: {e}")
        
        # Возвращаем информацию о платеже
        return {
            "success": True,
            "order_id": order_id,
            "payment_info": {
                "method": "kaspi",
                "phone": KASPI_PHONE,
                "manager_contact": f"ID менеджера: {MANAGER_ID}",
                "amount": price,
                "description": f"Оплата заказа #{order_id}: {pname}"
            },
            "message": f"✅ Заказ #{order_id} создан! Переведите {price} ₸ на номер {KASPI_PHONE}"
        }
        
    except Exception as e:
        import traceback
        print(f"❌ Ошибка при создании заказа: {e}")
        print(traceback.format_exc())
        return {
            "success": False,
            "error": f"Ошибка сервера: {str(e)}"
        }
