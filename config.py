LIRA_BOT_TOKEN = "8523482797:AAGb278OafpJfV0XMd6dp9qggsd2Tf_m_-M"
BOT_TOKEN = LIRA_BOT_TOKEN  # алиас для совместимости
BOT_USERNAME = "Lira_search_robot"
ADMIN_ID = 6044235905
BOT_NAME = "Lira"
SUPPORT_USERNAME = "@normoy"

AGREEMENT_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19"
PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-04-01-26"

FREE_ATTEMPTS = 6
ATTEMPTS_RESTORE_HOURS = 12
ATTEMPTS_RESTORE_COUNT = 6
FREE_MIN_LENGTH = 6

CRYPTOPAY_TOKEN = "576018:AAgKx9Fmve8656kElEg1extjgEU88GjEJj6"
CRYPTOPAY_API_URL = "https://pay.crypt.bot/api"

PREMIUM_PLANS = {
    "1d":    {"days": 1,    "stars": 15,   "label": "1 день"},
    "3d":    {"days": 3,    "stars": 40,   "label": "3 дня"},
    "7d":    {"days": 7,    "stars": 85,   "label": "7 дней"},
    "30d":   {"days": 30,   "stars": 300,  "label": "30 дней"},
    "365d":  {"days": 365,  "stars": 1000, "label": "365 дней"},
    "forever": {"days": 999999, "stars": 1700, "label": "Навсегда"},
}

CRYPTO_PLANS = {
    "1d":    0.30,
    "3d":    0.75,
    "7d":    1.50,
    "30d":   4.50,
    "365d":  15.00,
    "forever": 25.00,
}

DB_PATH = "lira.db"
