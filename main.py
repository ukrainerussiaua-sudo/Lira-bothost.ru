import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from config import LIRA_BOT_TOKEN, BOT_NAME
from database.db import init_db
from handlers import start, search, cabinet, premium, support
from middlewares.antiflood import AntiFloodMiddleware
from middlewares.subscription import SubscriptionMiddleware
from storage import SQLiteStorage   # <-- persistent FSM storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

LOCK_FILE = "/tmp/lira_bot.lock"


def acquire_lock():
    """Prevent multiple bot instances running at once."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            # PID 1 is always init/systemd — never our bot
            if pid == os.getpid() or pid == 1:
                raise ProcessLookupError
            os.kill(pid, 0)
            # Double-check: make sure it's actually a Python process
            cmdline_path = f"/proc/{pid}/cmdline"
            if os.path.exists(cmdline_path):
                with open(cmdline_path, "rb") as f:
                    cmdline = f.read().decode(errors="replace")
                if "python" not in cmdline.lower():
                    raise ProcessLookupError
            logging.error(f"Bot is already running (PID {pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def release_lock():
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


async def keepalive(bot):
    """Ping bot every 5 minutes to prevent hosting sleep."""
    while True:
        try:
            await asyncio.sleep(300)
            await bot.get_me()
        except Exception:
            pass


async def main():
    acquire_lock()
    try:
        await init_db()
        logging.info("Database initialized")
        bot = Bot(token=LIRA_BOT_TOKEN)

        # SQLiteStorage keeps FSM states across restarts
        # — admin panel, search wizard, everything survives reboot
        storage = SQLiteStorage()
        dp = Dispatcher(storage=storage)

        dp.message.middleware(AntiFloodMiddleware())
        dp.message.middleware(SubscriptionMiddleware())
        dp.callback_query.middleware(AntiFloodMiddleware())

        dp.include_router(start.router)
        dp.include_router(search.router)
        dp.include_router(cabinet.router)
        dp.include_router(premium.router)
        dp.include_router(support.router)

        await bot.delete_webhook(drop_pending_updates=True)
        logging.info(f"✅ {BOT_NAME} Search Bot started!")

        await asyncio.gather(
            keepalive(bot),
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        )
    finally:
        release_lock()

if __name__ == "__main__":
    asyncio.run(main())
