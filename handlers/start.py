from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (get_or_create_user, get_stats, create_promo,
                          is_admin, add_admin, remove_admin, get_all_admins,
                          get_all_user_ids)
from utils.keyboards import main_menu_kb, main_menu_kb_for, admin_kb
from config import ADMIN_ID, BOT_NAME, AGREEMENT_URL, PRIVACY_URL
from middlewares.subscription import is_subscribed, CHANNEL_LINK
import asyncio

router = Router()

class AdminStates(StatesGroup):
    waiting_broadcast = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    ref_id = None
    if message.text and "start=" in message.text:
        try:
            ref_id = int(message.text.split("start=")[1].strip())
            if ref_id == message.from_user.id:
                ref_id = None
        except Exception:
            ref_id = None

    if not await is_subscribed(message.bot, message.from_user.id):
        name = message.from_user.first_name or message.from_user.username or "друг"
        caption_text = "Привет, " + name + "!\n\nЧтобы пользоваться ботом — подпишись на канал"
        await message.answer_photo(
            photo="https://i.ibb.co/CswV2tZR/lira-search-prewiev.jpg",
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться", url=CHANNEL_LINK)],
                [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub_ref_" + str(ref_id or 0))],
            ])
        )
        return

    user, is_new = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
        referrer_id=ref_id
    )
    if ref_id and is_new:
        new_user_name = "@" + message.from_user.username if message.from_user.username else message.from_user.full_name or str(message.from_user.id)
        inviter_name = None
        try:
            inviter_chat = await message.bot.get_chat(ref_id)
            inviter_name = "@" + inviter_chat.username if inviter_chat.username else inviter_chat.full_name
        except Exception:
            pass
        # Сообщение новому пользователю
        if inviter_name:
            try:
                await message.bot.send_message(
                    message.from_user.id,
                    f"🎉 Ты пришёл по ссылке от {inviter_name}! Добро пожаловать 👋",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        # Сообщение пригласившему
        try:
            await message.bot.send_message(
                ref_id,
                f"🎉 По твоей реф-ссылке пришёл {new_user_name}! Спасибо за вклад в проект 🙏",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await message.answer(
        "<b>Лицензии и документы " + BOT_NAME + " Search</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пользовательское соглашение", url=AGREEMENT_URL)],
            [InlineKeyboardButton(text="Политика конфиденциальности", url=PRIVACY_URL)],
        ])
    )
    await message.answer(
        "<b>Приветствуем в " + BOT_NAME + " Search!</b>\n\nНаш бот — профессиональный инструмент для поиска свободных юзернеймов в Telegram.\n\nВыберите нужное действие в меню ниже:",
        parse_mode="HTML",
        reply_markup=await main_menu_kb_for(message.from_user.id)
    )

@router.message(F.text == "Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "<b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=await main_menu_kb_for(message.from_user.id)
    )

@router.message(F.text == "◀️ Главное меню")
async def back_to_main2(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "<b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=await main_menu_kb_for(message.from_user.id)
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    await _confirm_subscription(callback, ref_id=None)

@router.callback_query(F.data.startswith("check_sub_ref_"))
async def check_subscription_ref(callback: CallbackQuery):
    try:
        ref_id = int(callback.data.split("check_sub_ref_")[1])
        ref_id = ref_id if ref_id != 0 else None
    except Exception:
        ref_id = None
    await _confirm_subscription(callback, ref_id=ref_id)

async def _confirm_subscription(callback: CallbackQuery, ref_id):
    bot = callback.bot
    if await is_subscribed(bot, callback.from_user.id):
        await callback.message.delete()
        user, is_new = await get_or_create_user(
            user_id=callback.from_user.id,
            username=callback.from_user.username or "",
            full_name=callback.from_user.full_name or "",
            referrer_id=ref_id
        )
        if ref_id and is_new:
            new_user_name = "@" + callback.from_user.username if callback.from_user.username else callback.from_user.full_name or str(callback.from_user.id)
            inviter_name = None
            try:
                inviter_chat = await bot.get_chat(ref_id)
                inviter_name = "@" + inviter_chat.username if inviter_chat.username else inviter_chat.full_name
            except Exception:
                pass
            # Сообщение новому пользователю — кто пригласил
            try:
                if inviter_name:
                    await bot.send_message(
                        callback.from_user.id,
                        f"🎉 Ты пришёл по ссылке от <b>{inviter_name}</b>! Добро пожаловать 👋\n\n💎 Твой пригласитель получил +1 час Premium!",
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_message(
                        callback.from_user.id,
                        f"🎉 Ты пришёл по реферальной ссылке! Добро пожаловать 👋",
                        parse_mode="HTML"
                    )
            except Exception:
                pass
            # Сообщение пригласившему
            try:
                await bot.send_message(
                    ref_id,
                    f"🎉 По твоей реф-ссылке пришёл <b>{new_user_name}</b>!\n\n💎 Тебе начислен +1 час Premium! Спасибо за вклад 🙏",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await callback.message.answer(
            "<b>Подписка подтверждена!</b>\n\nДобро пожаловать в " + BOT_NAME + " Search!\nВыберите действие в меню ниже:",
            parse_mode="HTML",
            reply_markup=await main_menu_kb_for(callback.from_user.id)
        )
    else:
        await callback.answer("Вы ещё не подписались на канал!", show_alert=True)

async def _show_admin_panel(message: Message):
    total, premium, support_today, tiktok_pending = await get_stats()
    await message.answer(
        "<b>Админ панель " + BOT_NAME + "</b>\n\nПользователей: <b>" + str(total) + "</b>\nPremium: <b>" + str(premium) + "</b>\nОбращений сегодня: <b>" + str(support_today) + "</b>\nTikTok заявок: <b>" + str(tiktok_pending) + "</b>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )

@router.message(F.text == "🔧 Админ панель")
async def admin_panel_btn(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await _show_admin_panel(message)

@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await _show_admin_panel(message)

@router.message(F.text == "📊 Статистика")
async def stats_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return
    total, premium, support_today, tiktok_pending = await get_stats()
    await message.answer(
        "<b>Статистика " + BOT_NAME + "</b>\n\nПользователей: <b>" + str(total) + "</b>\nPremium: <b>" + str(premium) + "</b>\nОбращений сегодня: <b>" + str(support_today) + "</b>\nTikTok заявок: <b>" + str(tiktok_pending) + "</b>",
        parse_mode="HTML"
    )

@router.message(F.text == "🎫 Создать промокод")
async def create_promo_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "Введите промокод в формате:\n<code>PROMO_КОД ДНЕЙ ИСПОЛЬЗОВАНИЙ</code>\n\nПример: <code>LIRA30 30 5</code>",
        parse_mode="HTML"
    )

@router.message(F.text.regexp(r"^[A-Za-z0-9_]{3,20} \d+ \d+$"))
async def save_promo_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    code, days, uses = parts[0], int(parts[1]), int(parts[2])
    await create_promo(code, days, uses)
    await message.answer(
        "Промокод <code>" + code + "</code> создан!\nДней: " + str(days) + ", Использований: " + str(uses),
        parse_mode="HTML"
    )

@router.message(F.text == "📢 Рассылка")
async def broadcast_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    await message.answer(
        "<b>Рассылка всем пользователям</b>\n\nОтправьте сообщение для рассылки.\nНажмите Отмена для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.waiting_broadcast)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.text in ("Отмена", "◀️ Отмена", "◀️ Главное меню"):
        await state.clear()
        await _show_admin_panel(message)
        return

    await state.clear()
    user_ids = await get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0

    progress_msg = await message.answer("Отправляю... 0 / " + str(total))

    for i, uid in enumerate(user_ids, 1):
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            await asyncio.sleep(1)
            try:
                await progress_msg.edit_text("Отправляю... " + str(i) + " / " + str(total))
            except Exception:
                pass

    await progress_msg.edit_text(
        "<b>Рассылка завершена!</b>\n\nОтправлено: <b>" + str(sent) + "</b>\nОшибок: <b>" + str(failed) + "</b>\nВсего: <b>" + str(total) + "</b>",
        parse_mode="HTML"
    )
    await _show_admin_panel(message)

@router.message(F.text == "🛡 Управление админами")
async def manage_admins(message: Message):
    if not await is_admin(message.from_user.id):
        return
    admins = await get_all_admins()
    lines = "\n".join("• <code>" + str(a["user_id"]) + "</code> — с " + a["added_at"][:10] for a in admins)
    await message.answer(
        "<b>Администраторы бота</b>\n\n" + lines + "\n\nКоманды:\n/addadmin <code>USER_ID</code>\n/removeadmin <code>USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )

@router.message(Command("addadmin"))
async def add_admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /addadmin <code>USER_ID</code>", parse_mode="HTML")
        return
    target = int(parts[1])
    if target == ADMIN_ID:
        await message.answer("Вы уже главный администратор.")
        return
    await add_admin(target, message.from_user.id)
    await message.answer("Пользователь <code>" + str(target) + "</code> назначен администратором.", parse_mode="HTML")

@router.message(Command("removeadmin"))
async def remove_admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /removeadmin <code>USER_ID</code>", parse_mode="HTML")
        return
    target = int(parts[1])
    if target == ADMIN_ID:
        await message.answer("Нельзя снять главного администратора.")
        return
    await remove_admin(target)
    await message.answer("Пользователь <code>" + str(target) + "</code> снят с должности администратора.", parse_mode="HTML")
