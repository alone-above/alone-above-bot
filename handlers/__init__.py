"""handlers/__init__.py — регистрация всех роутеров"""
from aiogram import Router

from .start      import router as start_router
from .catalog    import router as catalog_router
from .profile    import router as profile_router
from .cart       import router as cart_router
from .orders     import router as orders_router
from .payment    import router as payment_router
from .reviews    import router as reviews_router
from .drops      import router as drops_router
from .partners   import router as partners_router
from .support    import router as support_router
from .ads        import router as ads_router
from .admin      import router as admin_router


def setup_routers(dp):
    """Подключить все роутеры к диспетчеру."""
    for r in [
        start_router,
        catalog_router,
        profile_router,
        cart_router,
        orders_router,
        payment_router,
        reviews_router,
        drops_router,
        partners_router,
        support_router,
        ads_router,
        admin_router,      # Всегда последним — имеет более широкие фильтры
    ]:
        dp.include_router(r)
