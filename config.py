"""
╔══════════════════════════════════════════════════════╗
║  SHOPBOT — config.py                                 ║
║  Конфигурация, константы, анимированные эмодзи       ║
╚══════════════════════════════════════════════════════╝
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Токены и ID ────────────────────────────────────────
# The bot token is required to start the bot. We allow a couple of common env var names
# (BOT_TOKEN is preferred, but some platforms use TELEGRAM_BOT_TOKEN).
BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TG_BOT_TOKEN")
)
if not BOT_TOKEN:
    raise RuntimeError(
        "Missing required env var: BOT_TOKEN (or TELEGRAM_BOT_TOKEN / TG_BOT_TOKEN). "
        "Set it in your environment or in a .env file."
    )

CRYPTOBOT_TOKEN  = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_IDS        = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@support")
SHOP_NAME        = os.getenv("SHOP_NAME", "👕 Магазин одежды")
KASPI_PHONE      = os.getenv("KASPI_PHONE", "+7XXXXXXXXXX")
MANAGER_ID       = int(os.getenv("MANAGER_ID", str(ADMIN_IDS[0])))

# ── PostgreSQL — Railway
# Внутренний URL (Railway internal network, быстрее, только внутри Railway)
DATABASE_INTERNAL_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:hbDPoVFnfBPweyFjjmWYdmOtgRBrtzyn@postgres.railway.internal:5432/railway"
)
# Публичный URL (для локальной разработки / внешнего доступа)
DATABASE_PUBLIC_URL = os.getenv(
    "DATABASE_PUBLIC_URL",
    "postgresql://postgres:hbDPoVFnfBPweyFjjmWYdmOtgRBrtzyn@yamabiko.proxy.rlwy.net:26709/railway"
)
# Используем: сначала внутренний, фоллбэк — публичный
DATABASE_URL = DATABASE_INTERNAL_URL

# ── Бизнес-настройки ───────────────────────────────────
USD_KZT_RATE:     float = 494.0
CASHBACK_PERCENT: float = 5.0
AD_PRICE_KZT:     float = 500.0

# ── Роли ───────────────────────────────────────────────
ROLES = {
    "buyer":   "🛒 Покупатель",
    "seller":  "🏪 Продавец",
    "owner":   "👑 Владелец",
    "manager": "🗂 Менеджер",
    "partner": "🤝 Партнёр",
    "support": "🎧 Поддержка",
}

# ── Промокоды — типы ───────────────────────────────────
PROMO_TYPES = {
    "discount_percent": "Скидка %",
    "discount_fixed":   "Скидка ₸",
    "gift":             "Подарок",
    "cashback_bonus":   "Бонус на счёт",
    "free_delivery":    "Бесплатная доставка",
    "special_offer":    "Спецпредложение",
}

# ── Статусы заказов ────────────────────────────────────
ORDER_STATUS_LABELS = {
    "processing": "🔄 В обработке",
    "china":      "✈️ Едет из Китая",
    "arrived":    "📦 Прибыло в Шымкент",
    "delivered":  "🚚 Передано покупателю",
    "confirmed":  "✅ Получено покупателем",
}

# ── Сообщения бота (дефолты) ───────────────────────────
BOT_MSG_DEFAULTS = {
    "welcome":        "👋 Добро пожаловать в {shop_name}!\n\nВыберите раздел ниже:",
    "catalog_header": "🛒 <b>Каталог</b>\n\n<blockquote>👇 Выберите категорию:</blockquote>",
    "profile_header": "👤 <b>Мой профиль</b>",
    "support_header": "❓ <b>Поддержка</b>\n\n<blockquote>По любым вопросам пишите нашему менеджеру.</blockquote>",
    "about_header":   "🏬 <b>О магазине</b>",
    "order_confirm":  "🎉 <b>Заказ #{order_id} оформлен!</b>\n\nОжидайте уведомлений о статусе.",
    "payment_wait":   "⏳ <b>Ожидаем подтверждения менеджера</b>\n\n<blockquote>Обычно это занимает несколько минут.</blockquote>",
    "drops_header":   "🔥 <b>Дропы</b>\n\n<blockquote>Скоро в продаже!</blockquote>",
    "partner_header": "🤝 <b>Партнёрская программа</b>\n\nПриглашай друзей и получай бонусы!",
}

BOT_MSG_KEYS_LABELS = {
    "welcome":        "👋 Приветствие (/start)",
    "catalog_header": "🛒 Заголовок каталога",
    "profile_header": "👤 Заголовок профиля",
    "support_header": "❓ Заголовок поддержки",
    "about_header":   "🏬 О магазине",
    "order_confirm":  "🎉 Подтверждение заказа",
    "payment_wait":   "⏳ Ожидание оплаты",
    "drops_header":   "🔥 Заголовок дропов",
    "partner_header": "🤝 Партнёрская программа",
}

# ── Навигационные коллбэки (сброс FSM) ────────────────
NAV_CALLBACKS = {
    "adm_panel", "adm_media", "adm_cats", "adm_products", "addprod",
    "adm_settings", "ad_warning", "partnership", "about_back",
    "adm_promos", "support_back", "support_contacts", "adm_users",
    "adm_roles", "adm_partners", "adm_drops", "adm_botmsgs",
}

# ══════════════════════════════════════════════
#  Премиум (анимированные) эмодзи
# ══════════════════════════════════════════════
AE: dict[str, str] = {
    # ── Основные ────────────────────────────────
    "shop":     '<tg-emoji emoji-id="5373052667671093676">🛍</tg-emoji>',
    "down":     '<tg-emoji emoji-id="5470177992950946662">👇</tg-emoji>',
    "folder":   '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    "money":    '<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji>',
    "cart":     '<tg-emoji emoji-id="5431499171045581032">🛒</tg-emoji>',
    "cal":      '<tg-emoji emoji-id="5431897022456145283">📆</tg-emoji>',
    "archive":  '<tg-emoji emoji-id="5431736674147114227">🗂</tg-emoji>',
    "store":    '<tg-emoji emoji-id="5265105755677159697">🏬</tg-emoji>',
    "support":  '<tg-emoji emoji-id="5467666648263564704">❓</tg-emoji>',
    "star":     '<tg-emoji emoji-id="5368324170671202286">⭐</tg-emoji>',
    "truck":    '<tg-emoji emoji-id="5431736674147114227">🚚</tg-emoji>',
    "size":     '<tg-emoji emoji-id="5400250414929041085">⚖️</tg-emoji>',
    "phone":    '<tg-emoji emoji-id="5467539229468793355">📞</tg-emoji>',
    "tag":      '<tg-emoji emoji-id="5890883384057533697">🏷</tg-emoji>',
    "gift":     '<tg-emoji emoji-id="5199749070830197566">🎁</tg-emoji>',
    "pin":      '<tg-emoji emoji-id="5983099415689171511">📍</tg-emoji>',
    "user":     '<tg-emoji emoji-id="5373012449597335010">👤</tg-emoji>',
    "promo":    '<tg-emoji emoji-id="5368324170671202286">🎟</tg-emoji>',
    # ── Эмоции / статусы ────────────────────────
    "heart":    '<tg-emoji emoji-id="5449505950283078474">❤️</tg-emoji>',
    "heart_w":  '<tg-emoji emoji-id="5451714942157724312">🤍</tg-emoji>',
    "fire":     '<tg-emoji emoji-id="5420315771991497307">🔥</tg-emoji>',
    "diamond":  '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>',
    "crown":    '<tg-emoji emoji-id="5467406098367521267">👑</tg-emoji>',
    "ok":       '<tg-emoji emoji-id="5427009714745517609">✅</tg-emoji>',
    "no":       '<tg-emoji emoji-id="5465665476971471368">❌</tg-emoji>',
    "plus":     '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    "minus":    '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    "search":   '<tg-emoji emoji-id="5188311512791393083">🔎</tg-emoji>',
    "home":     '<tg-emoji emoji-id="5465226866321268133">🏠</tg-emoji>',
    "sparkle":  '<tg-emoji emoji-id="5472164874886846699">✨</tg-emoji>',
    "stars":    '<tg-emoji emoji-id="5458799228719472718">🌟</tg-emoji>',
    "rocket":   '<tg-emoji emoji-id="5445284980978621387">🚀</tg-emoji>',
    "trophy":   '<tg-emoji emoji-id="5409008750893734809">🏆</tg-emoji>',
    "chat":     '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    "bell":     '<tg-emoji emoji-id="5242628160297641831">🔔</tg-emoji>',
    "note":     '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    "bag":      '<tg-emoji emoji-id="5380056101473492248">👜</tg-emoji>',
    "coin":     '<tg-emoji emoji-id="5379600444098093058">🪙</tg-emoji>',
    "cash":     '<tg-emoji emoji-id="5375296873982604963">💰</tg-emoji>',
    "key":      '<tg-emoji emoji-id="5330115548900501467">🔑</tg-emoji>',
    "refresh":  '<tg-emoji emoji-id="5264727218734524899">🔄</tg-emoji>',
    "confetti": '<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>',
    "ribbon":   '<tg-emoji emoji-id="5375152498656961898">🎀</tg-emoji>',
    "chart":    '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji>',
    "link":     '<tg-emoji emoji-id="5375129357373165375">🔗</tg-emoji>',
    "medal":    '<tg-emoji emoji-id="5334644364280866007">🏅</tg-emoji>',
    "wand":     '<tg-emoji emoji-id="5260426225599405269">🪄</tg-emoji>',
    "bulb":     '<tg-emoji emoji-id="5472146462362048818">💡</tg-emoji>',
    "mobile":   '<tg-emoji emoji-id="5407025283456835913">📱</tg-emoji>',
    "msg":      '<tg-emoji emoji-id="5472019095106886003">💌</tg-emoji>',
    "rainbow":  '<tg-emoji emoji-id="5427042798878610107">🌈</tg-emoji>',
    "box":      '<tg-emoji emoji-id="5884479287171485878">📦</tg-emoji>',
}

def ae(key: str) -> str:
    """Вернуть премиум-эмодзи по ключу."""
    return AE.get(key, "")
