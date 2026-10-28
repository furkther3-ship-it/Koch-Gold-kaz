import aiosqlite

DB_PATH = "casino.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 1000,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                spins INTEGER DEFAULT 3,
                referrer_id INTEGER,
                total_wagered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game TEXT,
                bet INTEGER,
                win INTEGER,
                multiplier REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    await ensure_columns()


async def ensure_columns():
    """Добавляет недостающие колонки в таблицу users, НЕ удаляя данные."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(users)") as c:
            cols = [row[1] for row in await c.fetchall()]

        needed = {
            "balance": "INTEGER DEFAULT 1000",
            "level": "INTEGER DEFAULT 1",
            "xp": "INTEGER DEFAULT 0",
            "spins": "INTEGER DEFAULT 3",
            "referrer_id": "INTEGER",
            "total_wagered": "INTEGER DEFAULT 0",
        }

        for col, definition in needed.items():
            if col not in cols:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                print(f"[DB] Добавлена колонка: {col}")

        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id, username, balance, level, xp, spins,
                      referrer_id, total_wagered
               FROM users WHERE user_id = ?""",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()


async def create_user(user_id: int, username: str, referrer_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users
               (user_id, username, balance, level, xp, spins, referrer_id, total_wagered)
               VALUES (?, ?, 1000, 1, 0, 3, ?, 0)""",
            (user_id, username, referrer_id)
        )
        await db.commit()
    return await get_user(user_id)


async def update_balance(user_id: int, new_balance: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (new_balance, user_id)
        )
        await db.commit()


async def update_spins(user_id: int, new_spins: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET spins = ? WHERE user_id = ?",
            (new_spins, user_id)
        )
        await db.commit()


async def add_xp(user_id: int, xp_delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT xp, level, balance, spins FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        xp, level, balance, spins = row
        new_xp = xp + xp_delta
        new_level = level
        reward = 0
        spins_reward = 0

        while new_xp >= new_level * 100:
            new_xp -= new_level * 100
            new_level += 1
            reward += 500 * new_level
            spins_reward += 1

        new_balance = balance + reward
        new_spins = spins + spins_reward

        await db.execute(
            """UPDATE users SET xp = ?, level = ?, balance = ?, spins = ?
               WHERE user_id = ?""",
            (new_xp, new_level, new_balance, new_spins, user_id)
        )
        await db.commit()

        return {
            "level": new_level,
            "xp": new_xp,
            "xp_to_next": new_level * 100,
            "reward": reward,
            "spins_reward": spins_reward,
            "balance": new_balance,
            "spins": new_spins,
        }


async def add_wagered(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET total_wagered = total_wagered + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def add_history(user_id: int, game: str, bet: int, win: int, multiplier: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO history (user_id, game, bet, win, multiplier)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, game, bet, win, multiplier)
        )
        await db.commit()


async def get_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT game, bet, win, multiplier, created_at
               FROM history WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit)
        ) as cursor:
            return await cursor.fetchall()


async def get_referrals_count(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0


async def get_leaderboard(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id, username, balance, level, total_wagered
               FROM users ORDER BY balance DESC LIMIT ?""",
            (limit,)
        ) as c1:
            by_balance = await c1.fetchall()
        async with db.execute(
            """SELECT u.user_id, u.username, COALESCE(SUM(h.win), 0) AS total_win
               FROM users u LEFT JOIN history h ON u.user_id = h.user_id
               GROUP BY u.user_id ORDER BY total_win DESC LIMIT ?""",
            (limit,)
        ) as c2:
            by_wins = await c2.fetchall()
        return {"by_balance": by_balance, "by_wins": by_wins}


async def get_all_users(limit: int = 200, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id, username, balance, level, xp, spins,
                      total_wagered, created_at
               FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset)
        ) as cursor:
            return await cursor.fetchall()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance) FROM users") as c:
            users_count, total_balance = await c.fetchone()
        async with db.execute("SELECT SUM(total_wagered) FROM users") as c:
            total_wagered = (await c.fetchone())[0]
        return {
            "users_count": users_count or 0,
            "total_balance": total_balance or 0,
            "total_wagered": total_wagered or 0,
        }


async def admin_set_balance(user_id: int, amount: int):
    await update_balance(user_id, amount)


async def admin_add_balance(user_id: int, amount: int):
    user = await get_user(user_id)
    if user is None:
        return None
    new_balance = user[2] + amount
    await update_balance(user_id, new_balance)
    return new_balance


async def admin_set_spins(user_id: int, spins: int):
    await update_spins(user_id, spins)


async def admin_set_level(user_id: int, level: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET level = ? WHERE user_id = ?",
            (level, user_id)
        )
        await db.commit()


async def admin_delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()