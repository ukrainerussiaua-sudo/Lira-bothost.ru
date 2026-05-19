"""
Резервная проверка Fragment через парсинг HTML страницы.
Используется когда API возвращает {"error":"Bad request"}.
"""
import asyncio
import aiohttp
import logging

logger = logging.getLogger(__name__)

FRAGMENT_PAGE_URL = "https://fragment.com/username/{}"
REQUEST_TIMEOUT = 6


async def check_fragment_page(session: aiohttp.ClientSession, username: str) -> bool:
    """
    Парсит HTML страницу fragment.com/username/X.
    Возвращает True если ник СВОБОДЕН, False если ЗАНЯТ.
    При ошибке — True (доверяем Telegram).
    """
    url = FRAGMENT_PAGE_URL.format(username)
    try:
        async with session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                logger.warning(f"[FRAG_PAGE] @{username} | HTTP {resp.status} — доверяем TG")
                return True

            html = await resp.text()

            # Занят: есть кнопка аукциона или "Taken"
            OCCUPIED_MARKERS = [
                "Place bid",
                "place-bid",
                "Make an offer",
                "username-status-taken",
                "This username is taken",
                "t-username-taken",
                "Place Bid",
            ]
            for marker in OCCUPIED_MARKERS:
                if marker in html:
                    logger.info(f"[FRAG_PAGE] @{username} | marker='{marker}' => ЗАНЯТ ❌")
                    return False

            # Свободен: явный маркер свободного ника
            FREE_MARKERS = [
                "username-status-available",
                "This username is available",
                "not found",
            ]
            for marker in FREE_MARKERS:
                if marker in html:
                    logger.info(f"[FRAG_PAGE] @{username} | marker='{marker}' => СВОБОДЕН ✅")
                    return True

            # Нет явных маркеров — доверяем Telegram
            logger.warning(f"[FRAG_PAGE] @{username} | нет маркеров — доверяем TG")
            return True

    except asyncio.TimeoutError:
        logger.warning(f"[FRAG_PAGE] @{username} | таймаут — доверяем TG")
        return True
    except Exception as e:
        logger.warning(f"[FRAG_PAGE] @{username} | ошибка: {e} — доверяем TG")
        return True
