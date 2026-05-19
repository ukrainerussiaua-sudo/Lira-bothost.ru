import re
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (get_user, restore_attempts, is_premium, apply_promo,
                          set_custom_hwid, save_tiktok_submission, set_tiktok_trusted,
                          is_admin, get_stats, activate_premium, resolve_tiktok,
                          get_pending_tiktok, save_payment, get_referred_users)
from utils.keyboards import cabinet_kb, main_menu_kb, trust_tiktok_kb, tiktok_decision_kb, admin_kb
from config import ADMIN_ID, BOT_NAME, DB_PATH, BOT_USERNAME
from datetime import datetime

router = Router()

BACK_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True)
HWID_STARS_COST = 10


class CabinetStates(StatesGroup):
    waiting_promo = State()
    waiting_hwid = State()
    waiting_tiktok_url = State()
    waiting_trust_user = State()
    waiting_give_premium = State()


async def _show_admin_panel(message: Message):
    total, premium, support_today, tiktok_pending = await get_stats()
    await message.answer(
        f"🔧 <b>Админ панель</b>\n\n"
        f"👥 Всего пользователей: <b>{total}</b>\n"
        f"💎 Premium: <b>{premium}</b>\n"
        f"📩 Обращений сегодня: <b>{support_today}</b>\n"
        f"📱 TikTok заявок: <b>{tiktok_pending}</b>",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


# ─── Личный кабинет ───────────────────────────────────────────────────────────
@router.message(F.text == "👤 Личный кабинет")
async def show_cabinet(message: Message, state: FSMContext):
    await state.clear()
    await restore_attempts(message.from_user.id)
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден. Нажми /start")
        return

    prem = is_premium(user)
    status = "💎 Premium" if prem else "💙 Обычный"
    if prem and user["premium_until"]:
        from database.db import _parse_dt as _pdt
        until = _pdt(user["premium_until"])
        if until.year > 2999:
            expires = "Навсегда"
        else:
            expires = until.strftime("%Y-%m-%d %H:%M:%S")
    else:
        expires = "Не активен"

    attempts_display = "∞" if prem else str(user['attempts'])
    hwid_display = user.get("custom_hwid") or user["hwid"]
    ref_link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
    tiktok_trusted = bool(user.get("tiktok_trusted", 0))

    await message.answer(
        f"<b>Личный кабинет пользователя</b>\n"
        f"╔  🔑 <b>Ваш HWID:</b>\n"
        f"╚  <code>{hwid_display}</code>\n\n"
        f"Купить кастомный HWID: /hwid\n\n"
        f"╔  💎 <b>Статус:</b>  {status}\n"
        f"╠  🔍 <b>Попытки поиска:</b> {attempts_display}\n"
        f"╠  👥 <b>Приглашено друзей:</b> {user['referred_count']}\n"
        f"╠  🔗 <b>Реф. ссылка:</b>\n"
        f"╠  <code>{ref_link}</code>\n"
        f"╚  ⏳ <b>Premium до:</b> {expires}\n\n"
        + ("📱 <b>TikTok рефералы:</b> Нажми на кнопку ниже\n\n" if tiktok_trusted else "")
        + "💡 <i>Попытки восстанавливаются автоматически (+6 шт. каждые 12 часов).</i>",
        parse_mode="HTML",
        reply_markup=cabinet_kb(tiktok_trusted)
    )


# ─── /hwid команда ────────────────────────────────────────────────────────────
@router.message(F.text.startswith("/hwid"))
async def hwid_command(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Нажми /start сначала")
        return

    admin = await is_admin(message.from_user.id)

    if admin:
        # Admin gets it free
        await state.set_state(CabinetStates.waiting_hwid)
        current = user.get("custom_hwid") or user["hwid"]
        await message.answer(
            f"✏️ <b>Смена HWID (бесплатно для админа)</b>\n\n"
            f"Текущий: <code>{current}</code>\n\n"
            f"Введите новый HWID (буквы и цифры, до 16 символов):",
            parse_mode="HTML",
            reply_markup=BACK_KB
        )
    elif is_premium(user):
        # Premium: pay 10 stars
        current = user.get("custom_hwid") or user["hwid"]
        await message.answer(
            f"🔑 <b>Кастомный HWID</b>\n\n"
            f"Текущий: <code>{current}</code>\n\n"
            f"Смена стоит <b>{HWID_STARS_COST} ⭐</b>\n"
            f"Нажми кнопку ниже для оплаты:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ Оплатить {HWID_STARS_COST} Stars", callback_data="pay_hwid_stars")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_hwid")]
            ])
        )
    else:
        await message.answer(
            f"🔑 <b>Кастомный HWID</b>\n\n"
            f"Смена HWID доступна для <b>Premium</b> пользователей.\n"
            f"Стоимость: <b>{HWID_STARS_COST} ⭐</b>\n\n"
            f"💎 Купи Premium в разделе «Купить Premium»",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "pay_hwid_stars")
async def pay_hwid_invoice(callback: CallbackQuery):
    from aiogram.types import LabeledPrice
    await callback.message.answer_invoice(
        title="Кастомный HWID",
        description="Смена HWID на произвольное значение",
        payload=f"hwid_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="HWID смена", amount=HWID_STARS_COST)],
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_hwid")
async def cancel_hwid(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")


@router.message(F.successful_payment, F.successful_payment.invoice_payload.startswith("hwid_"))
async def hwid_payment_done(message: Message, state: FSMContext):
    await save_payment(message.from_user.id, "hwid", "stars", f"{HWID_STARS_COST} XTR")
    await state.set_state(CabinetStates.waiting_hwid)
    user = await get_user(message.from_user.id)
    current = user.get("custom_hwid") or user["hwid"]
    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n\n"
        f"Текущий HWID: <code>{current}</code>\n\n"
        f"Введите новый HWID (буквы и цифры, до 16 символов):",
        parse_mode="HTML",
        reply_markup=BACK_KB
    )


@router.message(CabinetStates.waiting_hwid)
async def process_hwid(message: Message, state: FSMContext):
    if message.text in ("◀️ Назад", "◀️ Главное меню"):
        await state.clear()
        await show_cabinet(message, state)
        return
    hwid = message.text.strip().upper()
    if not hwid.isalnum() or len(hwid) > 16 or len(hwid) < 4:
        await message.answer("❌ Только буквы и цифры, от 4 до 16 символов.")
        return
    await set_custom_hwid(message.from_user.id, hwid)
    await state.clear()
    user = await get_user(message.from_user.id)
    tiktok_trusted = bool(user.get("tiktok_trusted", 0)) if user else False
    await message.answer(f"✅ HWID изменён: <code>{hwid}</code>", parse_mode="HTML",
                         reply_markup=cabinet_kb(tiktok_trusted))


# ─── Промокод ─────────────────────────────────────────────────────────────────
@router.message(F.text == "🎫 Ввести промокод")
async def ask_promo(message: Message, state: FSMContext):
    await state.set_state(CabinetStates.waiting_promo)
    await message.answer("🎫 Введите промокод:", reply_markup=BACK_KB)


@router.message(CabinetStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    if message.text in ("◀️ Назад", "◀️ Главное меню"):
        await state.clear()
        await show_cabinet(message, state)
        return
    ok, result = await apply_promo(message.from_user.id, message.text.strip())
    user = await get_user(message.from_user.id)
    tiktok_trusted = bool(user.get("tiktok_trusted", 0)) if user else False
    if ok:
        await message.answer(f"✅ Промокод активирован!\n💎 Premium на {result} дней добавлен!",
                             parse_mode="HTML", reply_markup=cabinet_kb(tiktok_trusted))
    else:
        await message.answer(f"❌ {result}", reply_markup=cabinet_kb(tiktok_trusted))
    await state.clear()


# ─── Мои рефералы ─────────────────────────────────────────────────────────────
@router.message(F.text == "👥 Мои рефералы")
async def show_my_refs(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Нажми /start сначала")
        return

    refs = await get_referred_users(message.from_user.id)
    total = len(refs)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"

    if total == 0:
        await message.answer(
            f"👥 <b>Мои рефералы</b>\n\n"
            f"У вас пока нет приглашённых пользователей.\n\n"
            f"🔗 Ваша реф. ссылка:\n<code>{ref_link}</code>\n\n"
            f"💡 За каждого приглашённого — <b>+1 час Premium!</b>",
            parse_mode="HTML",
            reply_markup=cabinet_kb(bool(user.get("tiktok_trusted")))
        )
        return

    # Считаем сколько из рефералов купили premium
    premium_count = 0
    lines = []
    for r in refs[:20]:  # показываем max 20
        uname = f"@{r['username']}" if r.get("username") else f"id{r['user_id']}"
        has_prem = bool(r.get("premium_until"))
        if has_prem:
            premium_count += 1
        prem_icon = "💎" if has_prem else "👤"
        date = r["created_at"][:10] if r.get("created_at") else "?"
        lines.append(f"{prem_icon} {uname} — {date}")

    list_text = "\n".join(lines)
    more = f"\n<i>...и ещё {total - 20}</i>" if total > 20 else ""

    await message.answer(
        f"👥 <b>Мои рефералы</b>\n\n"
        f"📊 Всего приглашено: <b>{total}</b>\n"
        f"💎 Купили Premium: <b>{premium_count}</b>\n\n"
        f"{list_text}{more}\n\n"
        f"🔗 Ваша реф. ссылка:\n<code>{ref_link}</code>\n\n"
        f"💡 За каждого приглашённого — <b>+1 час Premium!</b>",
        parse_mode="HTML",
        reply_markup=cabinet_kb(bool(user.get("tiktok_trusted")))
    )


# ─── TikTok рефералы ──────────────────────────────────────────────────────────
@router.message(F.text == "📱 TikTok рефералы")
async def tiktok_ref(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user or not user.get("tiktok_trusted"):
        await message.answer("❌ Эта функция вам недоступна.")
        return
    await state.set_state(CabinetStates.waiting_tiktok_url)
    await message.answer(
        f"📱 <b>TikTok рефералы</b>\n\n"
        f"Отправьте ссылку на TikTok-видео с упоминанием бота.\n"
        f"Если наберёт <b>400+ просмотров</b> — получишь <b>+1 день Premium!</b>\n\n"
        f"🔗 Отправьте ссылку:",
        parse_mode="HTML",
        reply_markup=BACK_KB
    )


@router.message(CabinetStates.waiting_tiktok_url)
async def process_tiktok_url(message: Message, state: FSMContext):
    if message.text in ("◀️ Назад", "◀️ Главное меню"):
        await state.clear()
        await show_cabinet(message, state)
        return
    url = message.text.strip()
    if "tiktok.com" not in url and "vm.tiktok" not in url:
        await message.answer("❌ Отправьте корректную ссылку TikTok.")
        return
    await save_tiktok_submission(message.from_user.id, url)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT MAX(id) FROM tiktok_submissions WHERE user_id=?",
                               (message.from_user.id,)) as c:
            sid = (await c.fetchone())[0]

    user = await get_user(message.from_user.id)
    uname = f"@{user['username']}" if user and user.get("username") else str(message.from_user.id)
    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"📱 <b>Новая TikTok заявка #{sid}</b>\n\n"
            f"👤 {uname} (<code>{message.from_user.id}</code>)\n"
            f"🔗 {url}",
            parse_mode="HTML",
            reply_markup=tiktok_decision_kb(sid)
        )
    except Exception:
        pass
    await message.answer("✅ Заявка отправлена! Ожидайте решения.", reply_markup=cabinet_kb(True))
    await state.clear()


# ─── TikTok admin callbacks ───────────────────────────────────────────────────
@router.callback_query(F.data.startswith("tiktok_approve_"))
async def tiktok_approve(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    sid = int(callback.data.replace("tiktok_approve_", ""))
    user_id = await resolve_tiktok(sid, True)
    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b> — +1 день Premium", parse_mode="HTML")
    if user_id:
        try:
            await callback.bot.send_message(user_id,
                "✅ <b>TikTok заявка одобрена!</b>\n💎 +1 день Premium добавлен!", parse_mode="HTML")
        except Exception:
            pass
    await callback.answer("Одобрено!")


@router.callback_query(F.data.startswith("tiktok_reject_"))
async def tiktok_reject(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    sid = int(callback.data.replace("tiktok_reject_", ""))
    user_id = await resolve_tiktok(sid, False)
    await callback.message.edit_text(callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>", parse_mode="HTML")
    if user_id:
        try:
            await callback.bot.send_message(user_id,
                "❌ <b>TikTok заявка отклонена.</b>\nВидео не набрало 400+ просмотров.", parse_mode="HTML")
        except Exception:
            pass
    await callback.answer("Отклонено!")


# ─── Admin: Доверить TikTok ───────────────────────────────────────────────────
@router.message(F.text == "🔑 Доверить TikTok")
async def admin_trust_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(CabinetStates.waiting_trust_user)
    await message.answer("👤 Введите ID или @username пользователя:", reply_markup=BACK_KB)


@router.message(CabinetStates.waiting_trust_user)
async def admin_trust_tiktok(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    if message.text in ("◀️ Назад", "◀️ Главное меню"):
        await state.clear()
        await _show_admin_panel(message)
        return
    text = message.text.strip().lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if text.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id=?", (int(text),)) as c:
                user = await c.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username=?", (text,)) as c:
                user = await c.fetchone()
    if not user:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        await _show_admin_panel(message)
        return
    user = dict(user)
    uname = f"@{user['username']}" if user.get("username") else str(user["user_id"])
    await message.answer(
        f"👤 {uname}\n📱 TikTok: {'✅ Есть' if user.get('tiktok_trusted') else '❌ Нет'}\nВыберите действие:",
        reply_markup=trust_tiktok_kb(user["user_id"])
    )
    await state.clear()


@router.callback_query(F.data.startswith("trust_tiktok_"))
async def trust_tiktok_cb(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    parts = callback.data.split("_")
    user_id = int(parts[2])
    trusted = parts[3] == "1"
    await set_tiktok_trusted(user_id, trusted)
    status = "✅ Доверен" if trusted else "❌ Отозван"
    await callback.message.edit_text(callback.message.text + f"\n\n{status}")
    msg = ("✅ <b>Вам открыт доступ к TikTok рефералам!</b>" if trusted
           else "❌ <b>Доступ к TikTok рефералам отозван.</b>")
    try:
        await callback.bot.send_message(user_id, msg, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Готово!")


# ─── Admin: TikTok заявки ─────────────────────────────────────────────────────
@router.message(F.text == "📋 TikTok заявки")
async def admin_tiktok_list(message: Message):
    if not await is_admin(message.from_user.id):
        return
    items = await get_pending_tiktok()
    if not items:
        await message.answer("📋 Нет заявок на рассмотрении.")
        return
    for item in items:
        uname = f"@{item['username']}" if item.get("username") else str(item["user_id"])
        await message.answer(
            f"📱 <b>TikTok заявка #{item['id']}</b>\n\n"
            f"👤 {uname} (<code>{item['user_id']}</code>)\n"
            f"🔗 {item['tiktok_url']}\n"
            f"📅 {item['created_at'][:16]}",
            parse_mode="HTML",
            reply_markup=tiktok_decision_kb(item["id"])
        )


# ─── Admin: Выдать Premium ────────────────────────────────────────────────────
@router.message(F.text == "👑 Выдать Premium")
async def admin_give_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.set_state(CabinetStates.waiting_give_premium)
    await message.answer(
        "👑 Формат: <code>ID_или_@username ДНЕЙ</code>\nПример: <code>123456 30</code>",
        parse_mode="HTML",
        reply_markup=BACK_KB
    )


@router.message(CabinetStates.waiting_give_premium)
async def admin_give_premium(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    if message.text in ("◀️ Главное меню", "◀️ Назад"):
        await state.clear()
        await _show_admin_panel(message)
        return
    m = re.match(r"^(@?\w+)\s+(\d+)$", message.text.strip())
    if not m:
        await message.answer("❌ Неверный формат. Пример: <code>123456 30</code>", parse_mode="HTML")
        return
    target, days = m.group(1).lstrip("@"), int(m.group(2))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if target.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id=?", (int(target),)) as c:
                user = await c.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username=?", (target,)) as c:
                user = await c.fetchone()
    if not user:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        await _show_admin_panel(message)
        return
    user = dict(user)
    await activate_premium(user["user_id"], days)
    uname = f"@{user['username']}" if user.get("username") else str(user["user_id"])
    await message.answer(f"✅ {uname} — выдан Premium на {days} дней!")
    try:
        await message.bot.send_message(
            user["user_id"],
            f"🎁 <b>Вам выдан Premium на {days} дней!</b>\n💎 Приятного использования.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await state.clear()
    await _show_admin_panel(message)


# ─── Admin: Статистика ────────────────────────────────────────────────────────
@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await _show_admin_panel(message)
