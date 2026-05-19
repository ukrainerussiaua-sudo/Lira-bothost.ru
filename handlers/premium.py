from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import get_user, activate_premium, save_payment, is_premium, save_crypto_invoice, get_crypto_invoice, complete_crypto_invoice
from utils.keyboards import premium_plans_kb, payment_method_kb, main_menu_kb_for, crypto_check_kb
from utils.cryptopay import create_invoice, check_invoice
from config import PREMIUM_PLANS, CRYPTO_PLANS, ADMIN_ID, BOT_NAME

router = Router()


def get_plan_key(text: str):
    for key, plan in PREMIUM_PLANS.items():
        if plan["label"] in text and str(plan["stars"]) in text:
            return key
    return None


class PremiumStates(StatesGroup):
    choosing_plan = State()
    choosing_method = State()


@router.message(F.text == "💎 Купить Premium")
async def show_premium(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    premium_status = "✅ У вас активен Premium!\n\n" if user and is_premium(user) else ""
    await message.answer(
        f"💎 <b>{BOT_NAME} Premium</b>\n\n"
        f"Выберите тариф:\n\n"
        f"💎 <b>Что даёт Premium:</b>\n"
        f"• Неограниченный поиск\n"
        f"• Доступ к 5-буквенным никам\n"
        f"• Выбор prefix (до 3 букв) и suffix (до 2 букв)\n"
        f"• Приоритетная поддержка\n\n"
        f"{premium_status}💙 {BOT_NAME} Search",
        parse_mode="HTML",
        reply_markup=premium_plans_kb()
    )
    await state.set_state(PremiumStates.choosing_plan)


@router.message(PremiumStates.choosing_plan, F.text == "◀️ Главное меню")
async def premium_back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("💎 <b>Главное меню</b>", parse_mode="HTML",
                         reply_markup=await main_menu_kb_for(message.from_user.id))


@router.message(PremiumStates.choosing_plan, F.text.contains("💎") & F.text.contains("⭐"))
async def choose_plan(message: Message, state: FSMContext):
    plan_key = get_plan_key(message.text)
    if not plan_key:
        await message.answer("❌ Выберите тариф из меню.")
        return
    plan = PREMIUM_PLANS[plan_key]
    crypto_price = CRYPTO_PLANS[plan_key]
    await state.update_data(plan_key=plan_key)
    await state.set_state(PremiumStates.choosing_method)
    await message.answer(
        f"💎 <b>Тариф: {plan['label']}</b>\n\n"
        f"⭐ Telegram Stars: <b>{plan['stars']} XTR</b>\n"
        f"💳 CryptoBot USDT: <b>{crypto_price} USDT</b>\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=payment_method_kb(plan_key)
    )


# ─── Stars payment ────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    plan_key = callback.data.replace("pay_stars_", "")
    plan = PREMIUM_PLANS.get(plan_key)
    if not plan:
        await callback.answer("Ошибка тарифа")
        return
    await callback.message.answer_invoice(
        title=f"{BOT_NAME} Premium — {plan['label']}",
        description=f"Неограниченный поиск ников + доступ к 5-буквенным никам",
        payload=f"premium_{plan_key}_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{BOT_NAME} Premium {plan['label']}", amount=plan["stars"])],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment, F.successful_payment.invoice_payload.startswith("premium_"))
async def successful_payment(message: Message, state: FSMContext):
    payload = message.successful_payment.invoice_payload
    plan_key = None
    for key in PREMIUM_PLANS.keys():
        if f"premium_{key}_" in payload:
            plan_key = key
            break
    if not plan_key:
        await message.answer("❌ Ошибка платежа. Обратитесь в поддержку.")
        return
    plan = PREMIUM_PLANS[plan_key]
    await activate_premium(message.from_user.id, plan["days"])
    await save_payment(message.from_user.id, plan_key, "stars", str(plan["stars"]) + " XTR")
    await message.answer(
        f"✅ <b>Premium активирован!</b>\n\n💎 Тариф: {plan['label']}\n🚀 Неограниченный поиск доступен!\n\n💙 {BOT_NAME} Search",
        parse_mode="HTML",
        reply_markup=await main_menu_kb_for(message.from_user.id)
    )
    await state.clear()


# ─── CryptoBot payment ────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery, state: FSMContext):
    plan_key = callback.data.replace("pay_crypto_", "")
    plan = PREMIUM_PLANS.get(plan_key)
    crypto_price = CRYPTO_PLANS.get(plan_key, 0)
    if not plan:
        await callback.answer("Ошибка тарифа")
        return

    await callback.answer("Создаю счёт...", show_alert=False)

    payload = f"lira_{plan_key}_{callback.from_user.id}"
    invoice = await create_invoice(
        amount=crypto_price,
        asset="USDT",
        description=f"{BOT_NAME} Premium — {plan['label']}",
        payload=payload
    )

    if not invoice:
        await callback.message.answer(
            "❌ Не удалось создать счёт CryptoBot. Попробуйте позже или выберите оплату Stars.",
            reply_markup=await main_menu_kb_for(callback.from_user.id)
        )
        return

    invoice_id = str(invoice["invoice_id"])
    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")

    await save_crypto_invoice(invoice_id, callback.from_user.id, plan_key, str(crypto_price))
    await save_payment(callback.from_user.id, plan_key, "crypto", f"{crypto_price} USDT")

    await callback.message.answer(
        f"💳 <b>Оплата через CryptoBot</b>\n\n"
        f"Тариф: <b>{plan['label']}</b>\n"
        f"Сумма: <b>{crypto_price} USDT</b>\n\n"
        f"1. Нажми кнопку ниже — откроется @CryptoBot\n"
        f"2. Оплати счёт\n"
        f"3. Вернись и нажми «✅ Я оплатил»\n\n"
        f"🔗 <a href='{pay_url}'>Открыть счёт в CryptoBot</a>",
        parse_mode="HTML",
        reply_markup=crypto_check_kb(invoice_id, plan_key),
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("crypto_check_"))
async def crypto_check(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    invoice_id = parts[2]
    plan_key = parts[3]

    status = await check_invoice(int(invoice_id))
    if status == "paid":
        inv = await get_crypto_invoice(invoice_id)
        if inv and inv["status"] == "pending":
            plan = PREMIUM_PLANS.get(plan_key)
            if plan:
                await activate_premium(callback.from_user.id, plan["days"])
                await complete_crypto_invoice(invoice_id)
                await callback.message.edit_text(
                    f"✅ <b>Premium активирован!</b>\n\n💎 Тариф: {plan['label']}\n🚀 Приятного использования!\n\n💙 {BOT_NAME} Search",
                    parse_mode="HTML"
                )
                await callback.message.answer("💎 Главное меню", reply_markup=await main_menu_kb_for(callback.from_user.id))
                await callback.answer("✅ Оплата подтверждена!")
                return
        else:
            await callback.answer("✅ Уже активировано!")
            return
    elif status == "active":
        await callback.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.", show_alert=True)
    elif status == "expired":
        await callback.answer("❌ Счёт истёк. Создай новый.", show_alert=True)
    else:
        await callback.answer("❌ Не удалось проверить. Попробуй позже.", show_alert=True)


@router.callback_query(F.data == "back_premium")
async def back_premium(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PremiumStates.choosing_plan)
    await callback.message.answer(
        f"💎 <b>{BOT_NAME} Premium</b>\n\nВыберите тариф:",
        parse_mode="HTML",
        reply_markup=premium_plans_kb()
    )
    await callback.answer()
