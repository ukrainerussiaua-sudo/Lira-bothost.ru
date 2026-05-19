import asyncio
import random
import string
import aiohttp
import json
import logging
from utils.fragment_check import check_fragment_page

logger = logging.getLogger(__name__)

TELEGRAM_CHECK_URL = "https://t.me/{}"
FRAGMENT_API_URL = "https://fragment.com/api/usernames/resolve"
LETTERS = string.ascii_lowercase
LETTERS_DIGITS = string.ascii_lowercase + string.digits

BATCH_SIZE = 20
MAX_TRIES = 600
REQUEST_TIMEOUT = 5
SEARCH_TIMEOUT = 55


def _fragment_status_free(status: str, raw: str, username: str) -> bool:
    """
    not_found   = СВОБОДЕН ✅  (ник не существует на Fragment)
    unavailable = СВОБОДЕН ✅  (Fragment не может проверить = ошибка API, доверяем Telegram)
    available   = ЗАНЯТ ❌     (на аукционе Fragment)
    taken       = ЗАНЯТ ❌     (кем-то занят на Telegram)
    sold        = ЗАНЯТ ❌     (продан через Fragment)
    for_sale    = ЗАНЯТ ❌     (выставлен на продажу)
    пусто       = не рискуем = ЗАНЯТ ❌
    """
    status_clean = status.strip().lower() if status else ""

    logger.info(f"[FRAGMENT] @{username} | status='{status_clean}' | raw='{raw[:120]}'")

    if not status_clean:
        logger.warning(f"[FRAGMENT] @{username} | Пустой статус — доверяем Telegram")
        return True  # пусть Telegram решает

    # Свободные статусы
    FREE_STATUSES = {"not_found", "unavailable"}
    if status_clean in FREE_STATUSES:
        logger.info(f"[FRAGMENT] @{username} | '{status_clean}' = СВОБОДЕН ✅")
        return True

    # Занятые статусы: available (аукцион), taken, sold, for_sale и всё остальное
    logger.info(f"[FRAGMENT] @{username} | '{status_clean}' = ЗАНЯТ ❌")
    return False


async def check_username_telegram(session: aiohttp.ClientSession, username: str) -> bool:
    try:
        async with session.get(
            TELEGRAM_CHECK_URL.format(username),
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            allow_redirects=True
        ) as resp:
            text = await resp.text()
            if "tgme_page_title" in text or "If you have Telegram" in text:
                logger.info(f"[TELEGRAM] @{username} | ЗАНЯТ ❌")
                return False
            logger.info(f"[TELEGRAM] @{username} | СВОБОДЕН ✅")
            return True
    except Exception as e:
        logger.warning(f"[TELEGRAM] @{username} | Ошибка: {e}")
        return False


async def check_username_fragment(session: aiohttp.ClientSession, username: str) -> bool:
    try:
        async with session.post(
            FRAGMENT_API_URL,
            json={"username": username},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://fragment.com",
                "Referer": "https://fragment.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            raw = await resp.text()

            logger.info(f"[FRAGMENT] @{username} | HTTP {resp.status} | raw='{raw[:200]}'")

            # Fragment вернул HTML вместо JSON — API недоступен, доверяем Telegram
            if raw and "<" in raw and "{" not in raw:
                logger.warning(f"[FRAGMENT] @{username} | HTML ответ — доверяем Telegram")
                return True

            if resp.status == 404:
                try:
                    data = json.loads(raw)
                    return _fragment_status_free(data.get("status", ""), raw, username)
                except Exception:
                    logger.info(f"[FRAGMENT] @{username} | 404 без JSON = СВОБОДЕН ✅")
                    return True

            if resp.status != 200:
                logger.warning(f"[FRAGMENT] @{username} | HTTP {resp.status} — доверяем Telegram")
                return True

            try:
                data = json.loads(raw)
            except Exception as e:
                logger.warning(f"[FRAGMENT] @{username} | JSON parse error: {e} — доверяем Telegram")
                return True

            # API заблокировал запрос — используем парсинг страницы
            if data.get("error") == "Bad request" or not data.get("status"):
                logger.warning(f"[FRAGMENT] @{username} | API заблокирован — парсим страницу")
                return await check_fragment_page(session, username)

            return _fragment_status_free(data.get("status", ""), raw, username)

    except asyncio.TimeoutError:
        logger.warning(f"[FRAGMENT] @{username} | Таймаут — доверяем Telegram")
        return True
    except Exception as e:
        logger.warning(f"[FRAGMENT] @{username} | Ошибка: {e} — доверяем Telegram")
        return True


async def check_username_free(session: aiohttp.ClientSession, username: str) -> bool:
    tg_free, frag_free = await asyncio.gather(
        check_username_telegram(session, username),
        check_username_fragment(session, username),
    )
    result = tg_free and frag_free
    logger.info(f"[CHECK] @{username} | TG={tg_free} FRAG={frag_free} => {'СВОБОДЕН ✅' if result else 'ЗАНЯТ ❌'}")
    return result


def generate_username(length: int, with_digits: bool,
                      prefix: str = "", suffix: str = "", smart: bool = False) -> str:
    chars = LETTERS_DIGITS if with_digits else LETTERS
    fixed_len = len(prefix) + len(suffix)
    remaining = length - fixed_len
    if remaining <= 0:
        return (prefix + suffix)[:length]

    if smart:
        vowels = "aeiou"
        consonants = "bcdfghjklmnpqrstvwxyz"

        # Разные паттерны для красивых ников
        patterns = [
            "cvcvc",    # klasik, tonik
            "cvvcv",    # liaxa, kioma
            "ccvcc",    # traks, blink
            "cvcvv",    # kaleo, navio
            "vcvcv",    # okiro, amera
            "cvccv",    # karta, belka
            "ccvcv",    # brana, treka
            "vccvc",    # alfor, index
        ]

        def fill_pattern(pat: str) -> str:
            result = []
            for ch in pat:
                if ch == "c":
                    result.append(random.choice(consonants))
                else:
                    result.append(random.choice(vowels))
            return "".join(result)

        fixed_len = len(prefix) + len(suffix)
        remaining = length - fixed_len

        # Подбираем паттерн нужной длины или обрезаем
        suitable = [p for p in patterns if len(p) == remaining]
        if suitable:
            pat = random.choice(suitable)
            middle = fill_pattern(pat)
        else:
            # Генерируем по случайному паттерну нужной длины
            pat = "".join(random.choice("cv") for _ in range(remaining))
            middle = fill_pattern(pat)

        # Иногда добавляем двойную букву в любом месте (начало, конец, середина)
        if remaining >= 3 and random.random() < 0.4:
            double_pos = random.choice(["start", "end", "middle"])
            if double_pos == "start":
                middle = middle[0] + middle  # tt...
                middle = middle[:remaining]
            elif double_pos == "end":
                middle = middle + middle[-1]  # ...ll
                middle = middle[:remaining]
            else:
                pos = random.randint(1, len(middle) - 2)
                middle = middle[:pos] + middle[pos] + middle[pos:]
                middle = middle[:remaining]

        # Иногда добавляем цифру в конец если with_digits
        if with_digits and random.random() < 0.3:
            middle = middle[:-1] + random.choice("0123456789")

        # Первый символ всегда буква
        if not prefix and middle and middle[0].isdigit():
            middle = random.choice(consonants) + middle[1:]
    else:
        if prefix:
            middle = "".join(random.choices(chars, k=remaining))
        else:
            first = random.choice(LETTERS)
            if remaining == 1:
                middle = first
            else:
                middle = first + "".join(random.choices(chars, k=remaining - 1))

    return prefix + middle + suffix


async def _check_one(session: aiohttp.ClientSession, username: str) -> str | None:
    if await check_username_free(session, username):
        return username
    return None


async def find_free_username(length: int, with_digits: bool,
                              prefix: str = "", suffix: str = "",
                              max_tries: int = MAX_TRIES,
                              smart: bool = False) -> str | None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    connector = aiohttp.TCPConnector(limit=BATCH_SIZE * 2)

    async def _search():
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tried = 0
            while tried < max_tries:
                batch_size = min(BATCH_SIZE, max_tries - tried)
                batch = [
                    generate_username(length, with_digits, prefix=prefix, suffix=suffix, smart=smart)
                    for _ in range(batch_size)
                ]
                tried += batch_size
                results = await asyncio.gather(*[_check_one(session, u) for u in batch])
                for result in results:
                    if result is not None:
                        return result
        return None

    try:
        return await asyncio.wait_for(_search(), timeout=SEARCH_TIMEOUT)
    except asyncio.TimeoutError:
        return None
