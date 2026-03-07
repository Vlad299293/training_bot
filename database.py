"""
SQLite база данных для хранения упражнений, весов и истории тренировок
"""

import aiosqlite
import json
from datetime import date
from config import DB_PATH


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    muscle_group TEXT NOT NULL,
                    equipment TEXT DEFAULT 'штанга/гантели',
                    is_compound INTEGER DEFAULT 1,
                    notes TEXT DEFAULT '',
                    UNIQUE(user_id, name)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS working_weights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    weight REAL NOT NULL,
                    reps INTEGER,
                    updated_at TEXT DEFAULT (date('now')),
                    UNIQUE(user_id, exercise_name)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS workout_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    muscle_group TEXT NOT NULL,
                    date TEXT DEFAULT (date('now')),
                    duration_minutes INTEGER,
                    plan_json TEXT,
                    mood INTEGER DEFAULT NULL,
                    mood_notes TEXT DEFAULT ''
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS weights_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exercise_name TEXT NOT NULL,
                    weight REAL NOT NULL,
                    date TEXT DEFAULT (date('now'))
                )
            """)
            # Миграции — добавляем колонки если их нет
            try:
                await db.execute("ALTER TABLE workout_sessions ADD COLUMN mood INTEGER DEFAULT NULL")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE workout_sessions ADD COLUMN mood_notes TEXT DEFAULT ''")
            except Exception:
                pass
            await db.commit()

    # ── Упражнения ────────────────────────────────────────────────────────────

    async def add_exercise(self, user_id: int, name: str, muscle_group: str,
                           equipment: str = "штанга/гантели",
                           is_compound: bool = True, notes: str = "") -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO exercises "
                    "(user_id, name, muscle_group, equipment, is_compound, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, name, muscle_group, equipment, int(is_compound), notes)
                )
                await db.commit()
            return True
        except Exception:
            return False

    async def get_exercises(self, user_id: int, muscle_group: str = None) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if muscle_group:
                cursor = await db.execute(
                    "SELECT * FROM exercises WHERE user_id=? AND muscle_group=? ORDER BY is_compound DESC, name",
                    (user_id, muscle_group)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM exercises WHERE user_id=? ORDER BY muscle_group, is_compound DESC, name",
                    (user_id,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_exercise(self, user_id: int, name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM exercises WHERE user_id=? AND name=?", (user_id, name)
            )
            await db.commit()
        return True

    async def get_muscle_groups(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT muscle_group FROM exercises WHERE user_id=? ORDER BY muscle_group",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    # ── Рабочие веса ─────────────────────────────────────────────────────────

    async def set_weight(self, user_id: int, exercise_name: str,
                         weight: float, reps: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO working_weights "
                "(user_id, exercise_name, weight, reps, updated_at) "
                "VALUES (?, ?, ?, ?, date('now'))",
                (user_id, exercise_name, weight, reps)
            )
            await db.commit()

    async def get_weights(self, user_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT exercise_name, weight, reps FROM working_weights WHERE user_id=?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return {r[0]: {"weight": r[1], "reps": r[2]} for r in rows}

    async def get_weight(self, user_id: int, exercise_name: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT weight, reps FROM working_weights WHERE user_id=? AND exercise_name=?",
                (user_id, exercise_name)
            )
            row = await cursor.fetchone()
            return {"weight": row[0], "reps": row[1]} if row else None

    # ── История тренировок ────────────────────────────────────────────────────

    async def save_session(self, user_id: int, muscle_group: str,
                           duration: int, plan: dict,
                           mood: int = None, mood_notes: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO workout_sessions (user_id, muscle_group, duration_minutes, plan_json, mood, mood_notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, muscle_group, duration, json.dumps(plan, ensure_ascii=False), mood, mood_notes)
            )
            await db.commit()

    async def save_weight_history(self, user_id: int, exercise_name: str, weight: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO weights_history (user_id, exercise_name, weight) VALUES (?, ?, ?)",
                (user_id, exercise_name, weight)
            )
            await db.commit()

    async def get_weights_history(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT exercise_name, weight, updated_at FROM working_weights "
                "WHERE user_id=? ORDER BY exercise_name",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_weekly_sessions(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM workout_sessions WHERE user_id=? "
                "AND date >= date('now', '-6 days') ORDER BY date",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_weekly_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM workout_sessions WHERE user_id=? "
                "AND date >= date('now', '-6 days')",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0]

    async def get_sessions(self, user_id: int, limit: int = 10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM workout_sessions WHERE user_id=? ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Профиль питания ───────────────────────────────────────────────────────

    async def save_nutrition_profile(self, user_id: int, profile: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_profiles (
                    user_id INTEGER PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT (date('now'))
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO nutrition_profiles (user_id, profile_json, updated_at) "
                "VALUES (?, ?, date('now'))",
                (user_id, json.dumps(profile, ensure_ascii=False))
            )
            await db.commit()

    async def get_nutrition_profile(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_profiles (
                    user_id INTEGER PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT (date('now'))
                )
            """)
            cursor = await db.execute(
                "SELECT profile_json FROM nutrition_profiles WHERE user_id=?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None

    # ── Вес тела ──────────────────────────────────────────────────────────────

    async def save_body_weight(self, user_id: int, weight: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS body_weight (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    date TEXT DEFAULT (date('now'))
                )
            """)
            await db.execute(
                "INSERT INTO body_weight (user_id, weight) VALUES (?, ?)",
                (user_id, weight)
            )
            await db.commit()

    async def get_body_weight_history(self, user_id: int, limit: int = 10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS body_weight (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    date TEXT DEFAULT (date('now'))
                )
            """)
            cursor = await db.execute(
                "SELECT weight, date FROM body_weight WHERE user_id=? ORDER BY date DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [{"weight": r[0], "date": r[1]} for r in rows]

    async def get_latest_body_weight(self, user_id: int) -> float | None:
        history = await self.get_body_weight_history(user_id, limit=1)
        return history[0]["weight"] if history else None

    async def get_all_user_ids(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT user_id FROM workout_sessions"
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
