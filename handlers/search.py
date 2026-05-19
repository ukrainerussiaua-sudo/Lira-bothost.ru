import asyncio
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (
    get_user, use_attempt, restore_attempts, is_premium,
    save_search_settings, check_search_cooldown, update_last_search_at
)
from utils.keyboards import search_length_kb, filters_kb, main_menu_kb, main_menu_kb_for, search_mode_kb
from utils.searcher import find_free_username
from config import BOT_NAME

router = Router()


class SearchStates(StatesGroup):
    choosing_length = State()
    choosing_filter = State()
    choosing_prefix = State()
    choosing_suffix = State()
    choosing_search_mode = State()
    searching = State()


LENGTH_MAP = {
    "💎 5 букв (Premium)": 5,
    "🔷 6 букв": 6,
    "🔷 7 букв": 7,
}

_back_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="-"), KeyboardButton(text="◀️ Назад")]],
    resize_keyboard=True
)


@router.message(F.text == "🔍 Найти ник")
async def start_search(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    await restore_attempts(message.from_user.id)
    prem = is_premium(user) if user else False

    if user and user.get("last_search_length"):
        await state.update_data(
            with_digits=bool(user.get("last_search_digits", 0)),
            prefix=user.get("prefix", ""),
            suffix=user.get("suffix", ""),
        )

    await state.set_state(SearchStates.choosing_length)
    await message.answer(
        "💎 <b>Выберите длину ника:</b>",
        parse_mode="HTML",
        reply_markup=search_length_kb(prem)
    )


@router.message(SearchStates.choosing_length, F.text.in_(LENGTH_MAP.keys()))
async def choose_length(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    prem = is_premium(user) if user else False
    length = LENGTH_MAP[message.text]
    if length == 5 and not prem:
        await message.answer("🔴 <b>Только для Premium!</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    if data.get("with_digits") is None:
        await state.update_data(length=length, with_digits=False, prefix="", suffix="")
    else:
        await state.update_data(length=length)

    await _do_search(message, state)


# ─── Фильтры ──────────────────────────────────────────────────────────────────
@router.message(SearchStates.choosing_length, F.text == "🔵 Фильтры")
async def open_filters(message: Message, state: FSMContext):
    await state.set_state(SearchStates.choosing_filter)
    await message.answer(
        f"🔵 <b>Настройка фильтров поиска</b>\n\n• 🔢 С цифрами\n• 🔡 Без цифр\n\n💙 {BOT_NAME} Search",
        parse_mode="HTML",
        reply_markup=filters_kb()
    )


@router.message(SearchStates.choosing_filter, F.text.in_(["🔢 С цифрами", "🔡 Без цифр"]))
async def choose_filter(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    prem = is_premium(user) if user else False
    with_digits = message.text == "🔢 С цифрами"
    await state.update_data(with_digits=with_digits)

    # Префикс/суффикс теперь для всех
    await state.set_state(SearchStates.choosing_prefix)
    await message.answer(
        "✏️ <b>Начало ника (до 3 символов)</b>\n\nОтправь <code>-</code> чтобы пропустить",
        parse_mode="HTML",
        reply_markup=_back_kb
    )


@router.message(SearchStates.choosing_filter, F.text.in_(["◀️ Назад", "◀️ Главное меню"]))
async def back_from_filter(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                             reply_markup=await main_menu_kb_for(message.from_user.id))
        return
    user = await get_user(message.from_user.id)
    await state.set_state(SearchStates.choosing_length)
    await message.answer("💎 <b>Выберите длину ника:</b>", parse_mode="HTML",
                         reply_markup=search_length_kb(is_premium(user) if user else False))


@router.message(SearchStates.choosing_prefix)
async def choose_prefix(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                             reply_markup=await main_menu_kb_for(message.from_user.id))
        return
    if message.text == "◀️ Назад":
        await state.set_state(SearchStates.choosing_filter)
        await message.answer(
            f"🔵 <b>Настройка фильтров</b>\n\n• 🔢 С цифрами\n• 🔡 Без цифр",
            parse_mode="HTML",
            reply_markup=filters_kb()
        )
        return
    prefix = "" if message.text.strip() == "-" else message.text.strip().lower()
    if len(prefix) > 3:
        await message.answer("❌ Максимум 3 символа для начала ника.")
        return
    # Префикс не может начинаться с цифры
    if prefix and prefix[0].isdigit():
        await message.answer("❌ Начало ника не может быть цифрой.")
        return
    await state.update_data(prefix=prefix)
    await state.set_state(SearchStates.choosing_suffix)
    await message.answer(
        "✏️ <b>Конец ника (до 2 символов)</b>\n\nОтправь <code>-</code> чтобы пропустить",
        parse_mode="HTML",
        reply_markup=_back_kb
    )


@router.message(SearchStates.choosing_suffix)
async def choose_suffix(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                             reply_markup=await main_menu_kb_for(message.from_user.id))
        return
    if message.text == "◀️ Назад":
        await state.set_state(SearchStates.choosing_prefix)
        await message.answer(
            "✏️ <b>Начало ника (до 3 символов)</b>\n\nОтправь <code>-</code> чтобы пропустить",
            parse_mode="HTML", reply_markup=_back_kb)
        return
    suffix = "" if message.text.strip() == "-" else message.text.strip().lower()
    if len(suffix) > 2:
        await message.answer("❌ Максимум 2 символа для конца ника.")
        return
    await state.update_data(suffix=suffix)
    await state.set_state(SearchStates.choosing_search_mode)
    await message.answer(
        "🔍 <b>Выберите режим поиска:</b>\n\n"
        "🧠 <b>Умный</b> — перебирает редкие комбинации, выше шанс найти красивый ник\n"
        "⚡ <b>Обычный</b> — быстрый случайный перебор",
        parse_mode="HTML",
        reply_markup=search_mode_kb()
    )


@router.message(SearchStates.choosing_search_mode, F.text.in_(["🧠 Умный поиск", "⚡ Обычный поиск"]))
async def choose_search_mode(message: Message, state: FSMContext):
    smart = message.text == "🧠 Умный поиск"
    await state.update_data(smart_search=smart)
    await _do_search(message, state)


@router.message(SearchStates.choosing_search_mode, F.text == "◀️ Назад")
async def back_from_search_mode(message: Message, state: FSMContext):
    await state.set_state(SearchStates.choosing_suffix)
    await message.answer(
        "✏️ <b>Конец ника (до 2 символов)</b>\n\nОтправь <code>-</code> чтобы пропустить",
        parse_mode="HTML", reply_markup=_back_kb)


@router.message(SearchStates.choosing_search_mode, F.text == "◀️ Главное меню")
async def search_mode_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                         reply_markup=await main_menu_kb_for(message.from_user.id))


@router.message(SearchStates.searching)
async def search_in_progress(message: Message, state: FSMContext):
    """Блокируем все сообщения пока идёт поиск."""
    await message.answer("⏳ Поиск уже идёт, подождите...")

@router.message(SearchStates.choosing_length, F.text == "◀️ Главное меню")
async def search_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                         reply_markup=await main_menu_kb_for(message.from_user.id))

@router.message(SearchStates.choosing_length, F.text == "🗑 Сбросить фильтры")
async def reset_filters(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    prem = is_premium(user) if user else False
    await state.update_data(with_digits=None, prefix="", suffix="", length=None)
    await save_search_settings(message.from_user.id, None, True, "", "")
    await message.answer(
        "✅ <b>Фильтры сброшены!</b>\n\nВыберите длину ника:",
        parse_mode="HTML",
        reply_markup=search_length_kb(prem)
    )


async def _do_search(message: Message, state: FSMContext):
    user_id = message.from_user.id

    wait = await check_search_cooldown(user_id)
    if wait > 0:
        secs = int(wait) + 1
        await message.answer(
            f"⏳ <b>Подождите {secs} сек. перед следующим поиском.</b>",
            parse_mode="HTML"
        )
        return

    user = await get_user(user_id)
    prem = is_premium(user) if user else False
    data = await state.get_data()
    length = data.get("length") or 6
    with_digits = data.get("with_digits")
    if with_digits is None:
        with_digits = False
    prefix = data.get("prefix") or ""
    suffix = data.get("suffix") or ""
    smart_search = data.get("smart_search", False)

    if length == 5 and not prem:
        await message.answer(
            "🔴 <b>5-буквенные ники — только для Premium!</b>",
            parse_mode="HTML"
        )
        await state.set_state(SearchStates.choosing_length)
        return

    await save_search_settings(user_id, length, with_digits, prefix, suffix)

    if not prem:
        has_attempt = await use_attempt(user_id)
        if not has_attempt:
            await message.answer(
                "❌ <b>Попытки исчерпаны!</b>\n\n"
                "💎 Купи Premium для неограниченного поиска\n"
                "⏳ Или подожди (+6 каждые 12 часов)",
                parse_mode="HTML",
                reply_markup=await main_menu_kb_for(user_id)
            )
            await state.clear()
            return

    filter_label = "с цифрами" if with_digits else "без цифр"
    mode_label = "🧠 умный" if smart_search else "⚡ обычный"
    extra = (f" | начало: <code>{prefix}</code>" if prefix else "") + \
            (f" | конец: <code>{suffix}</code>" if suffix else "")

    await state.set_state(SearchStates.searching)
    status_msg = await message.answer(
        f"🔵 Ищу свободный ник {length} символов...\n"
        f"📋 Фильтр: {filter_label}{extra}\n"
        f"🔍 Режим: {mode_label} | Проверяю через Telegram + Fragment",
        parse_mode="HTML"
    )

    # Запускаем 2 параллельных поиска — умный и обычный, берём первый результат
    results = await asyncio.gather(
        find_free_username(length, with_digits, prefix=prefix, suffix=suffix, smart=True),
        find_free_username(length, with_digits, prefix=prefix, suffix=suffix, smart=False),
        return_exceptions=True
    )
    username = next((r for r in results if isinstance(r, str)), None)

    await update_last_search_at(user_id)
    await status_msg.delete()

    if username:
        await message.answer(
            f"💎 | {BOT_NAME} нашла @{username}\n\n"
            f"✅ Проверено: Telegram + Fragment\n"
            f"🏃 Забирай быстрее!",
            parse_mode="HTML",
            reply_markup=search_length_kb(prem)
        )
    else:
        await message.answer(
            "😔 Не удалось найти свободный ник за 25 секунд. Попробуй ещё раз!",
            parse_mode="HTML",
            reply_markup=search_length_kb(prem)
        )
    await state.set_state(SearchStates.choosing_length)
