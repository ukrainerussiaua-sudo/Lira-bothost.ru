import aiosqlite
import hashlib
from datetime import datetime, timedelta
from config import DB_PATH, FREE_ATTEMPTS, ATTEMPTS_RESTORE_HOURS, ATTEMPTS_RESTORE_COUNT, ADMIN_ID

SEARCH_COOLDOWN_SECONDS = 3


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                hwid TEXT UNIQUE,
                custom_hwid TEXT,
                status TEXT DEFAULT 'free',
                premium_until TEXT,
                attempts INTEGER DEFAULT 6,
                last_restore TEXT,
                referrer_id INTEGER,
                referred_count INTEGER DEFAULT 0,
                tiktok_trusted INTEGER DEFAULT 0,
                last_search_length INTEGER,
                last_search_digits INTEGER DEFAULT 1,
                prefix TEXT DEFAULT '',
                suffix TEXT DEFAULT '',
                last_search_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        for col, defval in [
            ("tiktok_trusted", "INTEGER DEFAULT 0"),
            ("last_search_length", "INTEGER"),
            ("last_search_digits", "INTEGER DEFAULT 1"),
            ("prefix", "TEXT DEFAULT ''"),
            ("suffix", "TEXT DEFAULT ''"),
            ("last_search_at", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {defval}")
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                days INTEGER,
                uses_left INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_usages (
                user_id INTEGER,
                code TEXT,
                used_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, code)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan TEXT,
                method TEXT,
                amount TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_stats (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tiktok_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crypto_invoices (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                plan_key TEXT,
                amount TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fsm_storage (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Главный админ всегда присутствует в таблице
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)",
            (ADMIN_ID, ADMIN_ID)
        )
        await db.commit()


def generate_hwid(user_id: int) -> str:
    raw = f"{user_id}-lira-secret"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def _parse_dt(s: str) -> datetime:
    """Парсит ISO datetime строку надёжно, без timezone проблем."""
    if not s:
        raise ValueError("empty")
    # Убираем timezone суффикс — работаем только в UTC
    s = s.replace("Z", "").split("+")[0].strip()
    # Убираем микросекунды если есть
    if "." in s:
        s = s[:19]
    return datetime.fromisoformat(s)


def is_premium(user: dict) -> bool:
    """
    Проверяет премиум. Надёжно обрабатывает любой формат даты.
    Если срок истёк — статус НЕ сбрасывается здесь (только при записи в БД).
    """
    if not user:
        return False
    if user.get("status") != "premium":
        return False
    try:
        until = _parse_dt(user.get("premium_until", ""))
        return until > datetime.utcnow()
    except Exception:
        return False


async def _reset_expired_premium(user_id: int):
    """Сбрасывает статус premium → free если срок истёк. Вызывается при get_user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT status, premium_until FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        status, premium_until = row
        if status != "premium":
            return
        if not premium_until:
            # Нет даты — сбрасываем
            await db.execute(
                "UPDATE users SET status='free' WHERE user_id=?", (user_id,)
            )
            await db.commit()
            return
        try:
            until = _parse_dt(premium_until)
            if until <= datetime.utcnow():
                await db.execute(
                    "UPDATE users SET status='free' WHERE user_id=?", (user_id,)
                )
                await db.commit()
        except Exception:
            # Дата не парсится — сбрасываем на всякий случай
            await db.execute(
                "UPDATE users SET status='free' WHERE user_id=?", (user_id,)
            )
            await db.commit()


async def get_or_create_user(user_id: int, username: str, full_name: str, referrer_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            user = await cur.fetchone()
        if user:
            await db.execute("UPDATE users SET username=?, full_name=? WHERE user_id=?",
                             (username, full_name, user_id))
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                result = dict(await cur.fetchone())
            await _reset_expired_premium(user_id)
            async with aiosqlite.connect(DB_PATH) as db2:
                db2.row_factory = aiosqlite.Row
                async with db2.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                    return dict(await cur.fetchone()), False
        hwid = generate_hwid(user_id)
        now = datetime.utcnow().isoformat()
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, hwid, last_restore, referrer_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, hwid, now, referrer_id, now))
        if referrer_id:
            await db.execute("UPDATE users SET referred_count = referred_count + 1 WHERE user_id = ?",
                             (referrer_id,))
        await db.commit()
        if referrer_id:
            await activate_premium_hours(referrer_id, 1)
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return dict(await cur.fetchone()), True


async def get_user(user_id: int):
    """Получает пользователя и автоматически сбрасывает истёкший премиум."""
    await _reset_expired_premium(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def restore_attempts(user_id: int):
    user = await get_user(user_id)
    if not user:
        return
    try:
        last = _parse_dt(user["last_restore"]) if user["last_restore"] else datetime.utcnow() - timedelta(hours=13)
    except Exception:
        last = datetime.utcnow() - timedelta(hours=13)
    now = datetime.utcnow()
    if (now - last).total_seconds() >= ATTEMPTS_RESTORE_HOURS * 3600:
        new_attempts = FREE_ATTEMPTS  # всегда восстанавливаем до базового лимита
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET attempts=?, last_restore=? WHERE user_id=?",
                             (new_attempts, now.isoformat(), user_id))
            await db.commit()


async def use_attempt(user_id: int) -> bool:
    await restore_attempts(user_id)
    user = await get_user(user_id)
    if not user:
        return False
    if is_premium(user):
        return True
    if user["attempts"] <= 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET attempts = attempts - 1 WHERE user_id = ?", (user_id,))
        await db.commit()
    return True


async def check_search_cooldown(user_id: int) -> float:
    user = await get_user(user_id)
    if not user or not user.get("last_search_at"):
        return 0.0
    try:
        last = _parse_dt(user["last_search_at"])
        elapsed = (datetime.utcnow() - last).total_seconds()
        remaining = SEARCH_COOLDOWN_SECONDS - elapsed
        return max(0.0, remaining)
    except Exception:
        return 0.0


async def update_last_search_at(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_search_at=? WHERE user_id=?",
            (datetime.utcnow().isoformat(), user_id)
        )
        await db.commit()


async def activate_premium_hours(user_id: int, hours: int):
    user = await get_user(user_id)
    now = datetime.utcnow()
    if user and is_premium(user) and user["premium_until"]:
        try:
            start = _parse_dt(user["premium_until"])
            if start < now:
                start = now
        except Exception:
            start = now
    else:
        start = now
    until = start + timedelta(hours=hours)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status='premium', premium_until=? WHERE user_id=?",
                         (until.isoformat(), user_id))
        await db.commit()


async def activate_premium(user_id: int, days: int):
    user = await get_user(user_id)
    now = datetime.utcnow()
    if user and is_premium(user) and user["premium_until"]:
        try:
            start = _parse_dt(user["premium_until"])
        except Exception:
            start = now
    else:
        start = now
    until = now + timedelta(days=999999) if days >= 999999 else start + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status='premium', premium_until=? WHERE user_id=?",
                         (until.isoformat(), user_id))
        await db.commit()


async def apply_promo(user_id: int, code: str) -> tuple:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        code_upper = code.upper()
        async with db.execute("SELECT * FROM promo_codes WHERE code = ?", (code_upper,)) as cur:
            promo = await cur.fetchone()
        if not promo:
            return False, "Промокод не найден"
        if promo["uses_left"] <= 0:
            return False, "Промокод исчерпан"
        async with db.execute(
            "SELECT 1 FROM promo_usages WHERE user_id = ? AND code = ?", (user_id, code_upper)
        ) as cur:
            already_used = await cur.fetchone()
        if already_used:
            return False, "Вы уже использовали этот промокод"
        await activate_premium(user_id, promo["days"])
        await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code_upper,))
        await db.execute("INSERT INTO promo_usages (user_id, code) VALUES (?, ?)", (user_id, code_upper))
        await db.commit()
        return True, promo["days"]


async def create_promo(code: str, days: int, uses: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO promo_codes (code, days, uses_left) VALUES (?,?,?)",
                         (code.upper(), days, uses))
        await db.commit()


async def set_custom_hwid(user_id: int, hwid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET custom_hwid=? WHERE user_id=?", (hwid, user_id))
        await db.commit()


async def save_payment(user_id: int, plan: str, method: str, amount: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO payments (user_id, plan, method, amount) VALUES (?,?,?,?)",
                         (user_id, plan, method, amount))
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE status='premium' AND premium_until > datetime('now')"
        ) as c:
            premium = (await c.fetchone())[0]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with db.execute("SELECT count FROM support_stats WHERE date=?", (today,)) as c:
            row = await c.fetchone()
            support_today = row[0] if row else 0
        async with db.execute("SELECT COUNT(*) FROM tiktok_submissions WHERE status='pending'") as c:
            tiktok_pending = (await c.fetchone())[0]
        return total, premium, support_today, tiktok_pending


async def increment_support_stat():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO support_stats (date, count) VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET count = count + 1
        """, (today,))
        await db.commit()


async def save_tiktok_submission(user_id: int, url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO tiktok_submissions (user_id, tiktok_url) VALUES (?,?)",
                         (user_id, url))
        await db.commit()


async def get_pending_tiktok():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.username FROM tiktok_submissions t LEFT JOIN users u ON t.user_id=u.user_id WHERE t.status='pending'"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def resolve_tiktok(submission_id: int, approved: bool):
    status = "approved" if approved else "rejected"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM tiktok_submissions WHERE id=?", (submission_id,)) as c:
            row = await c.fetchone()
        if row and approved:
            await activate_premium(row[0], 1)
        await db.execute("UPDATE tiktok_submissions SET status=? WHERE id=?", (status, submission_id))
        await db.commit()
        return row[0] if row else None


async def set_tiktok_trusted(user_id: int, trusted: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET tiktok_trusted=? WHERE user_id=?", (1 if trusted else 0, user_id))
        await db.commit()


async def save_search_settings(user_id: int, length, with_digits: bool, prefix: str = "", suffix: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_search_length=?, last_search_digits=?, prefix=?, suffix=? WHERE user_id=?",
            (length, 1 if with_digits else 0, prefix, suffix, user_id)
        )
        await db.commit()


async def save_crypto_invoice(invoice_id: str, user_id: int, plan_key: str, amount: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO crypto_invoices (invoice_id, user_id, plan_key, amount) VALUES (?,?,?,?)",
            (invoice_id, user_id, plan_key, amount)
        )
        await db.commit()


async def get_crypto_invoice(invoice_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM crypto_invoices WHERE invoice_id=?", (invoice_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def complete_crypto_invoice(invoice_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE crypto_invoices SET status='paid' WHERE invoice_id=?", (invoice_id,))
        await db.commit()


# ─── Admin management ─────────────────────────────────────────────────────────
async def is_admin(user_id: int) -> bool:
    # Главный админ из config всегда админ — даже если БД сбросилась
    if user_id == ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)) as c:
            return bool(await c.fetchone())


async def add_admin(user_id: int, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?,?)",
            (user_id, added_by)
        )
        await db.commit()


async def remove_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await db.commit()


async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, added_at FROM admins") as c:
            return [dict(r) for r in await c.fetchall()]


# ─── Broadcast ────────────────────────────────────────────────────────────────
async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as c:
            return [r[0] for r in await c.fetchall()]


# ─── Persistent FSM Storage helpers ───────────────────────────────────────────
async def fsm_get(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM fsm_storage WHERE key=?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else None


async def fsm_set(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO fsm_storage (key, value, updated_at) VALUES (?,?,datetime('now'))",
            (key, value)
        )
        await db.commit()


async def fsm_delete(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM fsm_storage WHERE key=?", (key,))
        await db.commit()


async def fsm_get_keys(prefix: str) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key FROM fsm_storage WHERE key LIKE ?", (prefix + "%",)) as c:
            return [r[0] for r in await c.fetchall()]


async def get_referred_users(user_id: int) -> list:
    """Получить список пользователей приглашённых данным юзером."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id, username, full_name, premium_until, created_at
               FROM users WHERE referrer_id=? ORDER BY created_at DESC""",
            (user_id,)
        ) as c:
            rows = await c.fetchall()
    return [dict(r) for r in rows]
