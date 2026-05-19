import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any, Awaitable

CHANNEL_USERNAME = "Lira_search"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"


async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception as e:
        logging.warning(f"[SUB CHECK] user_id={user_id} error: {e}")
        return True  # Если ошибка — пропускаем пользователя


def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ])


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.text and event.text.strip().startswith("/start"):
                return await handler(event, data)

        bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        if not await is_subscribed(bot, user_id):
            await event.answer(
                "👋 Привет!\n\n"
                "Чтобы пользоваться ботом — подпишись на наш канал.\n\n"
                "После подписки нажми «✅ Я подписался»",
                reply_markup=sub_keyboard()
            )
            return

        return await handler(event, data)
