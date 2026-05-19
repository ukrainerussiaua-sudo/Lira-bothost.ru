from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import PREMIUM_PLANS, SUPPORT_USERNAME

def main_menu_kb(is_admin_flag: bool = False):
    rows = [
        [KeyboardButton(text="🔍 Найти ник")],
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="💎 Купить Premium")],
        [KeyboardButton(text="📩 Поддержка")],
    ]
    if is_admin_flag:
        rows.append([KeyboardButton(text="🔧 Админ панель")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def main_menu_kb_for(user_id: int) -> ReplyKeyboardMarkup:
    """Always-correct version — checks admin status itself. Use this everywhere."""
    from database.db import is_admin
    admin = await is_admin(user_id)
    return main_menu_kb(admin)

def search_length_kb(is_prem: bool):
    rows = [
        [KeyboardButton(text="💎 5 букв (Premium)")],
        [KeyboardButton(text="🔷 6 букв"), KeyboardButton(text="🔷 7 букв")],
        [KeyboardButton(text="🔵 Фильтры"), KeyboardButton(text="🗑 Сбросить фильтры")],
        [KeyboardButton(text="◀️ Главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def search_mode_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🧠 Умный поиск"), KeyboardButton(text="⚡ Обычный поиск")],
        [KeyboardButton(text="◀️ Назад")],
    ], resize_keyboard=True)

def filters_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔢 С цифрами"), KeyboardButton(text="🔡 Без цифр")],
        [KeyboardButton(text="◀️ Назад")],
    ], resize_keyboard=True)

def cabinet_kb(tiktok_trusted: bool = False):
    rows = [
        [KeyboardButton(text="🎫 Ввести промокод")],
        [KeyboardButton(text="👥 Мои рефералы")],
    ]
    if tiktok_trusted:
        rows.append([KeyboardButton(text="📱 TikTok рефералы")])
    rows.append([KeyboardButton(text="◀️ Главное меню")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def premium_plans_kb():
    rows = []
    for key, plan in PREMIUM_PLANS.items():
        rows.append([KeyboardButton(text=f"💎 {plan['label']} — {plan['stars']} ⭐")])
    rows.append([KeyboardButton(text="◀️ Главное меню")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def payment_method_kb(plan_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars_{plan_key}")],
        [InlineKeyboardButton(text="💳 CryptoBot (USDT)", callback_data=f"pay_crypto_{plan_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_premium")],
    ])

def crypto_check_kb(invoice_id: str, plan_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"crypto_check_{invoice_id}_{plan_key}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_premium")],
    ])

def support_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
    ])

def back_main_kb(user_id: int = 0):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Главное меню")]], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🎫 Создать промокод")],
        [KeyboardButton(text="📋 TikTok заявки")],
        [KeyboardButton(text="👑 Выдать Premium")],
        [KeyboardButton(text="🔑 Доверить TikTok")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🛡 Управление админами")],
        [KeyboardButton(text="◀️ Главное меню")],
    ], resize_keyboard=True)

def tiktok_decision_kb(submission_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить (+1 день)", callback_data=f"tiktok_approve_{submission_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"tiktok_reject_{submission_id}"),
    ]])

def trust_tiktok_kb(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Доверить", callback_data=f"trust_tiktok_{user_id}_1"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"trust_tiktok_{user_id}_0"),
    ]])
