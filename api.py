"""
api.py — FastAPI для мини-аппа
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from db.catalog import get_categories, get_products, get_product
from db.cart import cart_get, wish_get
from db.users import get_user
from config import SHOP_NAME, SUPPORT_USERNAME, KASPI_PHONE, MANAGER_ID

app = FastAPI(title="ShopBot API", description="API для мини-аппа магазина")

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
