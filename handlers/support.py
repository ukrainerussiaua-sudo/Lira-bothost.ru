from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import get_user, increment_support_stat
from utils.keyboards import main_menu_kb_for, admin_kb
from config import ADMIN_ID, BOT_NAME

router = Router()

class SupportStates(StatesGroup):
    waiting_message = State()
    admin_replying = State()

@router.message(F.text == "📩 Поддержка")
async def show_support(message: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    await state.set_state(SupportStates.waiting_message)
    await message.answer(
        f"📩 <b>Поддержка {BOT_NAME} Search</b>\n\n"
        f"💙 Работает: 12:00 — 00:00 по МСК\n\n"
        f"Напишите ваш вопрос, и мы ответим как можно скорее:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@router.message(SupportStates.waiting_message)
async def handle_support_message(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                             reply_markup=await main_menu_kb_for(message.from_user.id))
        return
    user = await get_user(message.from_user.id)
    uname = f"@{user['username']}" if user and user.get("username") else str(message.from_user.id)
    await increment_support_stat()
    # Используем бота из контекста — без создания нового объекта
    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"📩 <b>Сообщение в поддержку</b>\n\n"
            f"👤 {uname} (<code>{message.from_user.id}</code>)\n\n"
            f"💬 {message.text}\n\n"
            f"↩️ Ответить: /reply_{message.from_user.id}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await message.answer(
        "✅ Ваше сообщение отправлено!\nОжидайте ответа.",
        reply_markup=await main_menu_kb_for(message.from_user.id)
    )
    await state.clear()

@router.message(F.text.regexp(r"^/reply_\d+"))
async def admin_reply_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = int(message.text.split("_")[1])
    await state.update_data(reply_to=user_id)
    await state.set_state(SupportStates.admin_replying)
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    await message.answer(
        f"✏️ Введите ответ пользователю <code>{user_id}</code>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(SupportStates.admin_replying)
async def admin_send_reply(message: Message, state: FSMContext):
    if message.text in ("◀️ Отмена", "◀️ Главное меню"):
        await state.clear()
        await message.answer("🔧 Отменено", reply_markup=admin_kb())
        return
    data = await state.get_data()
    user_id = data.get("reply_to")
    try:
        await message.bot.send_message(
            user_id,
            f"📩 <b>Ответ от поддержки {BOT_NAME}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}!", reply_markup=admin_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_kb())
    await state.clear()
