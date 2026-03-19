"""
keyboards/inline.py — Все инлайн-клавиатуры бота

Правило: в кнопках используются ТОЛЬКО премиум-эмодзи через icon_custom_emoji_id,
никаких обычных эмодзи в тексте кнопок.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Иконки для кнопок (только премиум emoji ID) ───────
ICO = {
    # Навигация
    "back":       "5893057118545646106",   # ◁ назад
    "home":       "5873147866364514353",   # 🏘 дом
    # Действия
    "ok":         "5870633910337015697",   # ✅ галочка
    "no":         "5870657884844462243",   # ❌ крестик
    "edit":       "5870676941614354370",   # 🖋 карандаш
    "delete":     "5870875489362513438",   # 🗑 мусорный бак
    "add":        "5884479287171485878",   # 📦 коробка
    "send":       "5963103826075456248",   # ⬆ отправить
    "download":   "6039802767931871481",   # ⬇ скачать
    # Разделы
    "shop":       "5373052667671093676",   # 🛍
    "profile":    "5870994129244131212",   # 👤
    "cart":       "5431499171045581032",   # 🛒
    "heart":      "5449505950283078474",   # ❤️
    "about":      "5265105755677159697",   # 🏬
    "support":    "5467666648263564704",   # ❓
    "phone":      "5467539229468793355",   # 📞
    "pin":        "6042011682497106307",   # 📍
    "link":       "5769289093221454192",   # 🔗
    "info":       "6028435952299413210",   # ℹ
    "chat":       "5465300082628763143",   # 💬
    "partner":    "5769289093221454192",   # 🔗
    "orders":     "5431499171045581032",   # 🛒
    "stats":      "5870921681735781843",   # 📊
    "gift":       "6032644646587338669",   # 🎁
    "crown":      "5467406098367521267",   # 👑
    "fire":       "5420315771991497307",   # 🔥
    "rocket":     "5445284980978621387",   # 🚀
    "sparkle":    "5472164874886846699",   # ✨
    "refresh":    "5345906554510012647",   # 🔄
    "money":      "5904462880941545555",   # 🪙
    "lock":       "6037249452824072506",   # 🔒
    "unlock":     "6037496202990194718",   # 🔓
    "bell":       "6039486778597970865",   # 🔔
    "promo":      "5886285355279193209",   # 🏷
    "file":       "5870528606328852614",   # 📁
    "settings":   "5870982283724328568",   # ⚙
    "users":      "5870772616305839506",   # 👥
    "megaphone":  "6039422865189638057",   # 📣
    "calendar":   "5890937706803894250",   # 📅
    "size":       "5400250414929041085",   # ⚖️
    "tag":        "5886285355279193209",   # 🏷
    "bag":        "5380056101473492248",   # 👜
    "folder":     "5433653135799228968",   # 📁
    "star":       "5368324170671202286",   # ⭐
}

def btn(text: str, callback_data: str = None, url: str = None,
        icon: str = None) -> InlineKeyboardButton:
    """Создать кнопку с опциональным премиум-эмодзи."""
    kwargs: dict = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if icon and icon in ICO:
        kwargs["icon_custom_emoji_id"] = ICO[icon]
    elif icon:
        # Если передан raw ID
        kwargs["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kwargs)


def kb(*rows, include_main: bool = True) -> InlineKeyboardMarkup:
    """Собрать InlineKeyboardMarkup из строк кнопок.

    По умолчанию добавляем кнопку «Главное меню» внизу, чтобы пользователь мог
    быстро вернуться на главный экран из любой вкладки.

    Если клавиатура уже содержит кнопку с callback_data='main', то не добавляем
    дублирующую.
    """
    markup = InlineKeyboardMarkup(inline_keyboard=list(rows))

    if include_main:
        has_main = any(
            (btn.callback_data == "main")
            for row in markup.inline_keyboard
            for btn in row
        )
        if not has_main:
            markup.inline_keyboard.append([btn("Главное меню", "main", icon="home")])

    return markup


# ── Главное меню ──────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    # Не добавляем кнопку «Главное меню» в самой главной клавиатуре.
    # Возвращаем стандартный набор кнопок:
    # Профиль / Корзина / Избранное + Каталог + О магазине / Поддержка.
    return kb(
        [btn("Профиль",   "profile_view", icon="profile")],
        [btn("Корзина",   "my_cart",      icon="cart"),
         btn("Избранное", "my_wishlist", icon="heart")],
        [btn("Каталог",    "shop",         icon="shop")],
        [btn("О магазине", "about",        icon="about"),
         btn("Поддержка",  "support",      icon="support")],
        include_main=False,
    )


# ── Кнопка «Назад» ────────────────────────────────────
def kb_back(cd: str = "main") -> InlineKeyboardMarkup:
    return kb([btn("Назад", cd, icon="back")])


# ── Кнопка «Назад в админку» ──────────────────────────
def kb_admin_back() -> InlineKeyboardMarkup:
    return kb([btn("Панель управления", "adm_panel", icon="home")])


# ── Панель администратора ─────────────────────────────
def kb_admin() -> InlineKeyboardMarkup:
    return kb(
        [btn("Статистика",    "adm_stats",     icon="stats")],
        [btn("Медиа",         "adm_media",     icon="file"),
         btn("Рассылка",      "adm_broadcast", icon="megaphone")],
        [btn("Товары",        "adm_products",  icon="add"),
         btn("Категории",     "adm_cats",      icon="folder")],
        [btn("Заказы",        "adm_orders",    icon="orders")],
        [btn("Промокоды",     "adm_promos",    icon="promo")],
        [btn("Пользователи",  "adm_users",     icon="users")],
        [btn("Партнёры",      "adm_partners",  icon="partner")],
        [btn("Дропы",         "adm_drops",     icon="fire")],
        [btn("Сообщения бота","adm_botmsgs",   icon="chat")],
        [btn("Лог / отчёт",   "adm_log",       icon="stats")],
        [btn("Настройки",     "adm_settings",  icon="settings")],
    )


# ── Соглашение ────────────────────────────────────────
def kb_agreement() -> InlineKeyboardMarkup:
    return kb(
        [btn("Публичная оферта",
             url="https://teletype.in/@aloneabove/R6n3kZPT77z", icon="file")],
        [btn("Политика конфиденциальности",
             url="https://teletype.in/@aloneabove/cC0sM1BcefC", icon="lock")],
        [btn("Пользовательское соглашение",
             url="https://teletype.in/@aloneabove/L8aD4zXVy6W", icon="file")],
        [btn("Принять и продолжить", "agree_terms", icon="ok")],
    )


# ── Профиль ───────────────────────────────────────────
def kb_profile(cart_cnt: int = 0, wish_cnt: int = 0) -> InlineKeyboardMarkup:
    cart_label = "Корзина" + (f" ({cart_cnt})" if cart_cnt else "")
    wish_label = "Избранное" + (f" ({wish_cnt})" if wish_cnt else "")
    return kb(
        [btn(cart_label,  "my_cart",          icon="cart"),
         btn(wish_label,  "my_wishlist",       icon="heart")],
        [btn("Телефон",   "profile_phone",     icon="phone"),
         btn("Адрес",     "profile_address",   icon="pin")],
        [btn("Мои заказы",        "my_orders",        icon="orders")],
        [btn("Партнёрская программа", "partner_program", icon="partner")],
    )


# ── Поддержка ─────────────────────────────────────────
def kb_support(support_username: str) -> InlineKeyboardMarkup:
    uname = support_username.lstrip("@")
    return kb(
        [btn("Написать в поддержку",
             url=f"https://t.me/{uname}", icon="chat")],
        [btn("Контакты",              "support_contacts",  icon="phone")],
        [btn("Пожаловаться на товар", "complaint_start",   icon="no")],
        [btn("Публичная оферта",
             url="https://teletype.in/@aloneabove/R6n3kZPT77z", icon="file")],
        [btn("Политика конфиденциальности",
             url="https://teletype.in/@aloneabove/cC0sM1BcefC", icon="lock")],
        [btn("Пользовательское соглашение",
             url="https://teletype.in/@aloneabove/L8aD4zXVy6W", icon="file")],
        [btn("Сайт / мини-апп",
             url="https://t.me/alone_above_bot/shop", icon="link")],
    )


# ── Товарная карточка ─────────────────────────────────
def kb_product(pid: int, in_wish: bool, gallery_len: int = 0) -> InlineKeyboardMarkup:
    rows = []
    # Показываем кнопки покупки/добавления в корзину и избранного.
    # Раньше убирали кнопку «Купить» и «В корзину» — теперь возвращаем, чтобы UX был понятным.
    rows.append([btn("Купить", f"buy_{pid}", icon="money"),
                 btn("В корзину", f"cart_add_{pid}", icon="cart")])

    wish_icon = "heart" if not in_wish else "no"
    wish_text = "В избранное" if not in_wish else "Убрать из избранного"
    rows.append([btn(wish_text,   f"wish_toggle_{pid}", icon=wish_icon)])
    if gallery_len > 0:
        rows.append([btn(f"Галерея ({gallery_len})", f"gallery_{pid}_0", icon="sparkle")])
    rows.append([btn("Отзывы",   f"reviews_{pid}", icon="star")])
    rows.append([btn("Назад",    "shop",            icon="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Выбор метода оплаты ───────────────────────────────
def kb_payment(pid: int, size: str, promo_code: str = "") -> InlineKeyboardMarkup:
    pc = f"_{promo_code}" if promo_code else ""
    return kb(
        [btn("CryptoPay (USDT)",  f"pay_crypto_{pid}_{size}{pc}", icon="money")],
        [btn("Kaspi переводом",   f"pay_kaspi_{pid}_{size}{pc}",  icon="phone")],
        [btn("Применить промокод",f"apply_promo_{pid}_{size}",    icon="promo")],
        [btn("Назад",             f"prod_{pid}",                  icon="back")],
    )
