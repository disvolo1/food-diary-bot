import aiosqlite
from datetime import datetime, date


DB_NAME = "food_diary.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                calories_goal REAL,
                protein_goal REAL,
                fat_goal REAL,
                carbs_goal REAL,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                amount REAL,
                amount_unit TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (telegram_id)
                    REFERENCES users (telegram_id)
            )
        """)

        await db.commit()


async def get_user(telegram_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        )

        return await cursor.fetchone()


async def create_user(telegram_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO users (
                telegram_id,
                created_at
            )
            VALUES (?, ?)
            """,
            (
                telegram_id,
                datetime.now().isoformat()
            )
        )

        await db.commit()


async def update_user_goals(
    telegram_id: int,
    calories: float,
    protein: float,
    fat: float,
    carbs: float
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE users
            SET
                calories_goal = ?,
                protein_goal = ?,
                fat_goal = ?,
                carbs_goal = ?
            WHERE telegram_id = ?
            """,
            (
                calories,
                protein,
                fat,
                carbs,
                telegram_id
            )
        )

        await db.commit()


async def add_meal(
    telegram_id: int,
    name: str,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
    amount: float | None = None,
    amount_unit: str | None = None
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            INSERT INTO meals (
                telegram_id,
                name,
                calories,
                protein,
                fat,
                carbs,
                amount,
                amount_unit,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                name,
                calories,
                protein,
                fat,
                carbs,
                amount,
                amount_unit,
                datetime.now().isoformat()
            )
        )

        await db.commit()

        return cursor.lastrowid


async def get_today_totals(telegram_id: int):

    today = date.today().isoformat()

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT
                COALESCE(SUM(calories), 0),
                COALESCE(SUM(protein), 0),
                COALESCE(SUM(fat), 0),
                COALESCE(SUM(carbs), 0)
            FROM meals
            WHERE telegram_id = ?
            AND date(created_at) = ?
            """,
            (
                telegram_id,
                today
            )
        )

        row = await cursor.fetchone()

        return {
            "calories": row[0] or 0,
            "protein": row[1] or 0,
            "fat": row[2] or 0,
            "carbs": row[3] or 0
        }


async def get_today_meals(telegram_id: int):

    today = date.today().isoformat()

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT *
            FROM meals
            WHERE telegram_id = ?
            AND date(created_at) = ?
            ORDER BY created_at ASC
            """,
            (
                telegram_id,
                today
            )
        )

        return await cursor.fetchall()


async def delete_last_meal(telegram_id: int):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT id
            FROM meals
            WHERE telegram_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (telegram_id,)
        )

        row = await cursor.fetchone()

        if not row:
            return False

        await db.execute(
            """
            DELETE FROM meals
            WHERE id = ?
            """,
            (row[0],)
        )

        await db.commit()

        return True
