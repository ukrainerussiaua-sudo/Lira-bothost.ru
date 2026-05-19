import time
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Any, Awaitable

WINDOW_SECONDS = 10
MAX_REQUESTS = 8
CLEANUP_INTERVAL = 300  # чистим память каждые 5 минут


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self):
        self.user_requests: dict[int, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    def _cleanup(self):
        now = time.monotonic()
        if now - self._last_cleanup < CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        # Удаляем пустые записи
        to_delete = [
            uid for uid, times in self.user_requests.items()
            if not times or now - max(times) > WINDOW_SECONDS * 2
        ]
        for uid in to_delete:
            del self.user_requests[uid]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            now = time.monotonic()
            self._cleanup()
            self.user_requests[user_id] = [
                t for t in self.user_requests[user_id] if now - t < WINDOW_SECONDS
            ]
            if len(self.user_requests[user_id]) >= MAX_REQUESTS:
                if isinstance(event, Message):
                    await event.answer("⚠️ Слишком много запросов. Подождите немного.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Слишком много запросов!", show_alert=True)
                return
            self.user_requests[user_id].append(now)

        return await handler(event, data)
