from __future__ import annotations

import datetime
import os
import re
import sqlite3
import threading
import uuid
from typing import Optional


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Quantity normalization (extracted from original connector)
# ---------------------------------------------------------------------------

_MEAL_UNIT_ALIASES = {
    "g": "g", "grama": "g", "gramas": "g", "gr": "g",
    "kg": "kg", "quilo": "kg", "quilos": "kg",
    "ml": "ml", "mililitro": "ml", "mililitros": "ml",
    "l": "l", "litro": "l", "litros": "l",
    "un": "unit", "und": "unit", "unidade": "unit", "unidades": "unit",
    "porcao": "portion", "porcoes": "portion", "porcaoes": "portion",
    "porcao(s)": "portion",
    "xicara": "cup", "xicaras": "cup",
    "colher": "tbsp", "colher de sopa": "tbsp", "colheres de sopa": "tbsp",
    "colher de cha": "tsp", "colheres de cha": "tsp",
}


def _normalize_text_for_lookup(value: str) -> str:
    text = str(value or "").strip().lower()
    replacements = str.maketrans({
        "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    })
    text = text.translate(replacements)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_first_float(raw_value) -> Optional[float]:
    match = re.search(r"(-?[0-9]+(?:[.,][0-9]+)?)", str(raw_value or ""))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _normalize_quantity_unit(raw_unit: str) -> str:
    normalized = _normalize_text_for_lookup(raw_unit)
    if not normalized:
        return "unit"
    for alias, canonical in _MEAL_UNIT_ALIASES.items():
        if normalized == alias or normalized.startswith(f"{alias} "):
            return canonical
    return normalized.split(" ")[0]


def parse_quantity_details(quantity: str) -> dict:
    """Parse a quantity string like '150 g' into amount and unit."""
    quantity_text = str(quantity or "").strip()
    if not quantity_text:
        raise ValueError("quantity is required")
    amount = _extract_first_float(quantity_text)
    if amount is None:
        raise ValueError("quantity must include a numeric value")
    if amount <= 0:
        raise ValueError("quantity must be greater than zero")
    unit_match = re.search(r"[-+]?[0-9]+(?:[.,][0-9]+)?\s*([^\d].*)?$", quantity_text)
    raw_unit = unit_match.group(1).strip() if unit_match and unit_match.group(1) else ""
    unit = _normalize_quantity_unit(raw_unit)
    return {"raw": quantity_text, "amount": amount, "unit": unit}


def normalize_quantity(quantity_details: dict) -> dict:
    """Normalize to base unit: kg→g, l→ml."""
    amount = float(quantity_details["amount"])
    unit = quantity_details["unit"]
    if unit == "kg":
        amount, unit = amount * 1000.0, "g"
    elif unit == "l":
        amount, unit = amount * 1000.0, "ml"
    if amount <= 0:
        raise ValueError("quantity must be greater than zero")
    return {"amount": round(amount, 2), "unit": unit}


# ---------------------------------------------------------------------------
# HealthStore
# ---------------------------------------------------------------------------

class HealthStore:
    """Thread-safe SQLite store for tasks, meals, exercises, expenses and bills."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
            )
        self._db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        directory = os.path.dirname(self._db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT 'Pessoal',
                    due_date TEXT,
                    tags TEXT NOT NULL DEFAULT '[]',
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_tasks_user
                    ON health_tasks (user_id, done, due_date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_meals (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    food TEXT NOT NULL,
                    meal_type TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    normalized_amount REAL,
                    normalized_unit TEXT,
                    calories REAL NOT NULL,
                    date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_meals_user_date
                    ON health_meals (user_id, date)
            """)
            # Migrations: add new columns if not present
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(health_meals)").fetchall()}
            if "meal_group_id" not in existing_cols:
                conn.execute("ALTER TABLE health_meals ADD COLUMN meal_group_id TEXT")
            if "calories_pending" not in existing_cols:
                conn.execute("ALTER TABLE health_meals ADD COLUMN calories_pending INTEGER DEFAULT 0")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_meals_group
                    ON health_meals (meal_group_id)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_exercises (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    calories REAL NOT NULL,
                    date TEXT NOT NULL,
                    observations TEXT NOT NULL DEFAULT '',
                    done INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_exercises_user_date
                    ON health_exercises (user_id, date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_exercises_user_activity
                    ON health_exercises (user_id, activity, date)
            """)
            # Financial tables (expenses, bills, income) are managed by FinanceStore.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_health_goals (
                    user_id TEXT PRIMARY KEY,
                    calorie_goal INTEGER NOT NULL DEFAULT 2400,
                    exercise_calorie_goal INTEGER NOT NULL DEFAULT 0,
                    exercise_time_goal INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)
            # Migration: add duration_minutes to existing health_exercises tables
            try:
                conn.execute("ALTER TABLE health_exercises ADD COLUMN duration_minutes INTEGER")
            except Exception:
                pass  # column already exists
            # Migration: add effort_level (0-10, optional) to existing health_exercises tables
            try:
                conn.execute("ALTER TABLE health_exercises ADD COLUMN effort_level INTEGER")
            except Exception:
                pass  # column already exists

    # ---- Tasks ----

    def create_task(
        self,
        user_id: str,
        task_name: str,
        project: str = "Pessoal",
        due_date: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> dict:
        import json
        task_id = uuid.uuid4().hex
        now = _utc_now_iso()
        clean_tags = json.dumps([str(t).strip() for t in (tags or []) if str(t).strip()])
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO health_tasks (id, user_id, task_name, project, due_date, tags, done, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (task_id, user_id, task_name.strip(), project.strip() or "Pessoal",
                 due_date, clean_tags, now, now),
            )
        return self._task_row_to_dict({
            "id": task_id, "user_id": user_id, "task_name": task_name.strip(),
            "project": project.strip() or "Pessoal", "due_date": due_date,
            "tags": clean_tags, "done": 0,
        })

    def list_tasks(
        self,
        user_id: str,
        n_days: int = 0,
        limit: int = 10,
        include_done: bool = False,
    ) -> list[dict]:
        today = datetime.date.today()
        cutoff = (today + datetime.timedelta(days=max(n_days, 0))).isoformat()
        with self._lock, self._connect() as conn:
            if include_done:
                rows = conn.execute(
                    "SELECT * FROM health_tasks WHERE user_id = ? ORDER BY due_date ASC, created_at ASC LIMIT ?",
                    (user_id, max(1, limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM health_tasks
                    WHERE user_id = ? AND done = 0
                      AND (due_date IS NULL OR due_date <= ?)
                    ORDER BY due_date ASC, created_at ASC
                    LIMIT ?
                    """,
                    (user_id, cutoff, max(1, limit)),
                ).fetchall()
        return [self._task_row_to_dict(r) for r in rows]

    def get_task(self, user_id: str, task_id: str) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM health_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
        return self._task_row_to_dict(row) if row else None

    def update_task(self, user_id: str, task_id: str, **kwargs) -> dict:
        import json
        now = _utc_now_iso()
        updates = ["updated_at = ?"]
        params: list = [now]
        if "task_name" in kwargs:
            name = str(kwargs["task_name"]).strip()
            if not name:
                raise ValueError("task_name cannot be empty")
            updates.append("task_name = ?")
            params.append(name)
        if "project" in kwargs:
            updates.append("project = ?")
            params.append(str(kwargs["project"]).strip() or "Pessoal")
        if "due_date" in kwargs:
            updates.append("due_date = ?")
            params.append(kwargs["due_date"])
        if "tags" in kwargs:
            clean_tags = json.dumps([str(t).strip() for t in (kwargs["tags"] or []) if str(t).strip()])
            updates.append("tags = ?")
            params.append(clean_tags)
        if "done" in kwargs:
            updates.append("done = ?")
            params.append(1 if kwargs["done"] else 0)
        params.extend([task_id, user_id])
        sql = f"UPDATE health_tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id!r} not found")
            row = conn.execute("SELECT * FROM health_tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task_row_to_dict(row)

    @staticmethod
    def _task_row_to_dict(row) -> dict:
        import json
        r = dict(row)
        try:
            tags = json.loads(r.get("tags") or "[]")
        except (ValueError, TypeError):
            tags = []
        return {
            "id": r["id"],
            "name": r["task_name"],
            "deadline": r.get("due_date"),
            "project": r.get("project", "Pessoal"),
            "tags": tags,
            "done": bool(r.get("done", 0)),
        }

    def delete_task(self, user_id: str, task_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM health_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
        return cursor.rowcount > 0

    # ---- Meals ----

    def create_meal(
        self,
        user_id: str,
        food: str,
        meal_type: str,
        quantity: str,
        calories: float,
        date: Optional[str] = None,
        normalized_amount: Optional[float] = None,
        normalized_unit: Optional[str] = None,
        meal_group_id: Optional[str] = None,
        calories_pending: bool = False,
    ) -> dict:
        meal_id = uuid.uuid4().hex
        now = _utc_now_iso()
        meal_date = date or datetime.date.today().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO health_meals
                  (id, user_id, food, meal_type, quantity, normalized_amount, normalized_unit, calories, date, created_at, meal_group_id, calories_pending)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (meal_id, user_id, food.strip(), meal_type, quantity, normalized_amount,
                 normalized_unit, calories, meal_date, now, meal_group_id, int(calories_pending)),
            )
        return {
            "id": meal_id,
            "food": food.strip(),
            "meal_type": meal_type,
            "quantity": quantity,
            "normalized_amount": normalized_amount,
            "normalized_unit": normalized_unit,
            "calories": calories,
            "date": meal_date,
            "meal_group_id": meal_group_id,
            "calories_pending": calories_pending,
        }

    def list_meals_by_date_range(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 300,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM health_meals
                WHERE user_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, start_date[:10], end_date[:10], max(1, limit)),
            ).fetchall()
        return [self._meal_row_to_dict(r) for r in rows]

    @staticmethod
    def _meal_row_to_dict(row) -> dict:
        r = dict(row)
        return {
            "id": r["id"],
            "food": r["food"],
            "meal_type": r["meal_type"],
            "quantity": r["quantity"],
            "normalized_amount": r.get("normalized_amount"),
            "normalized_unit": r.get("normalized_unit"),
            "calories": float(r["calories"]),
            "date": r["date"],
            "meal_group_id": r.get("meal_group_id"),
            "calories_pending": bool(r.get("calories_pending", 0)),
        }

    def update_meal(self, user_id: str, meal_id: str, **kwargs) -> dict:
        updates = []
        params: list = []
        for col in ("food", "meal_type", "quantity", "date"):
            if col in kwargs:
                val = str(kwargs[col]).strip()
                if col in ("food", "meal_type", "quantity") and not val:
                    raise ValueError(f"{col} cannot be empty")
                updates.append(f"{col} = ?")
                params.append(val)
        if "calories" in kwargs:
            updates.append("calories = ?")
            params.append(float(kwargs["calories"]))
        if not updates:
            raise ValueError("At least one field to update is required")
        params.extend([meal_id, user_id])
        sql = f"UPDATE health_meals SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Meal {meal_id!r} not found")
            row = conn.execute("SELECT * FROM health_meals WHERE id = ?", (meal_id,)).fetchone()
        return self._meal_row_to_dict(row)

    def update_meal_calories_batch(self, meal_group_id: str, meal_ids: list[str], calories_list: list[float]) -> None:
        """Update calories for a list of meal items belonging to the same group.

        Sets calories_pending=0 on each updated item.
        meal_ids and calories_list must have the same length.
        """
        if len(meal_ids) != len(calories_list):
            raise ValueError("meal_ids and calories_list must have the same length")
        with self._lock, self._connect() as conn:
            for meal_id, cal in zip(meal_ids, calories_list):
                conn.execute(
                    "UPDATE health_meals SET calories = ?, calories_pending = 0 WHERE id = ?",
                    (cal, meal_id),
                )

    def delete_meal(self, user_id: str, meal_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM health_meals WHERE id = ? AND user_id = ?",
                (meal_id, user_id),
            )
        return cursor.rowcount > 0

    def delete_meal_group(self, user_id: str, meal_group_id: str) -> int:
        """Delete all meal items belonging to a group. Returns count of deleted rows."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM health_meals WHERE meal_group_id = ? AND user_id = ?",
                (meal_group_id, user_id),
            )
        return cursor.rowcount

    def update_meal_group(self, user_id: str, meal_group_id: str, **kwargs) -> int:
        """Update meal_type and/or date for all items in a group. Returns count of updated rows."""
        updates = []
        params: list = []
        for col in ("meal_type", "date"):
            if col in kwargs:
                val = str(kwargs[col]).strip()
                if not val:
                    raise ValueError(f"{col} cannot be empty")
                updates.append(f"{col} = ?")
                params.append(val)
        if not updates:
            raise ValueError("At least one field to update is required (meal_type or date)")
        params.extend([meal_group_id, user_id])
        sql = f"UPDATE health_meals SET {', '.join(updates)} WHERE meal_group_id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
        return cursor.rowcount

    def get_distinct_foods(self, user_id: str, limit: int = 200) -> list[str]:
        """Return distinct food names for a user, ordered by frequency (most used first)."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT food, COUNT(*) AS cnt
                FROM health_meals
                WHERE user_id = ?
                GROUP BY food
                ORDER BY cnt DESC, food ASC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [r["food"] for r in rows]

    # ---- Exercises ----
    def create_exercise(
        self,
        user_id: str,
        activity: str,
        calories: float,
        date: Optional[str] = None,
        observations: str = "",
        done: Optional[bool] = None,
        duration_minutes: Optional[int] = None,
        effort_level: Optional[int] = None,
    ) -> dict:
        exercise_id = uuid.uuid4().hex
        now = _utc_now_iso()
        exercise_date = date or datetime.date.today().isoformat()
        if done is None:
            try:
                done = datetime.date.fromisoformat(exercise_date) <= datetime.date.today()
            except ValueError:
                done = True
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO health_exercises
                  (id, user_id, activity, calories, date, observations, done, duration_minutes, effort_level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (exercise_id, user_id, activity.strip(), calories, exercise_date,
                 observations or "", 1 if done else 0, duration_minutes, effort_level, now, now),
            )
        return {
            "id": exercise_id,
            "activity": activity.strip(),
            "calories": calories,
            "date": exercise_date,
            "observations": observations or "",
            "done": done,
            "duration_minutes": duration_minutes,
            "effort_level": effort_level,
        }

    def update_exercise(self, user_id: str, exercise_id: str, **kwargs) -> dict:
        now = _utc_now_iso()
        updates = ["updated_at = ?"]
        params: list = [now]
        if "activity" in kwargs:
            a = str(kwargs["activity"]).strip()
            if not a:
                raise ValueError("activity cannot be empty")
            updates.append("activity = ?")
            params.append(a)
        if "calories" in kwargs:
            updates.append("calories = ?")
            params.append(float(kwargs["calories"]))
        if "date" in kwargs:
            updates.append("date = ?")
            params.append(str(kwargs["date"]))
        if "observations" in kwargs:
            updates.append("observations = ?")
            params.append(str(kwargs["observations"] or ""))
        if "done" in kwargs:
            updates.append("done = ?")
            params.append(1 if kwargs["done"] else 0)
        if "duration_minutes" in kwargs:
            dm = kwargs["duration_minutes"]
            updates.append("duration_minutes = ?")
            params.append(int(dm) if dm is not None else None)
        if "effort_level" in kwargs:
            el = kwargs["effort_level"]
            updates.append("effort_level = ?")
            params.append(int(el) if el is not None else None)
        params.extend([exercise_id, user_id])
        sql = f"UPDATE health_exercises SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Exercise {exercise_id!r} not found")
            row = conn.execute("SELECT * FROM health_exercises WHERE id = ?", (exercise_id,)).fetchone()
        return self._exercise_row_to_dict(row)

    def list_exercises_by_date_range(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 300,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM health_exercises
                WHERE user_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
                LIMIT ?
                """,
                (user_id, start_date[:10], end_date[:10], max(1, limit)),
            ).fetchall()
        return [self._exercise_row_to_dict(r) for r in rows]

    def find_exercise_duplicate(
        self, user_id: str, activity: str, date: str
    ) -> Optional[dict]:
        normalized = activity.strip().lower()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM health_exercises WHERE user_id = ? AND date = ?",
                (user_id, date[:10]),
            ).fetchall()
        for row in rows:
            if str(row["activity"] or "").strip().lower() == normalized:
                return self._exercise_row_to_dict(row)
        return None

    @staticmethod
    def _exercise_row_to_dict(row) -> dict:
        r = dict(row)
        return {
            "id": r["id"],
            "activity": r["activity"],
            "calories": float(r["calories"]),
            "date": r["date"],
            "observations": r.get("observations", ""),
            "done": bool(r.get("done", 1)),
            "duration_minutes": r.get("duration_minutes"),
            "effort_level": r.get("effort_level"),
        }

    def delete_exercise(self, user_id: str, exercise_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM health_exercises WHERE id = ? AND user_id = ?",
                (exercise_id, user_id),
            )
        return cursor.rowcount > 0

    def get_health_goals(self, user_id: str) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_health_goals WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row:
            r = dict(row)
            return {
                "calorie_goal": r["calorie_goal"],
                "exercise_calorie_goal": r["exercise_calorie_goal"],
                "exercise_time_goal": r["exercise_time_goal"],
            }
        return {"calorie_goal": 2400, "exercise_calorie_goal": 0, "exercise_time_goal": 0}

    def set_health_goals(
        self,
        user_id: str,
        calorie_goal: Optional[int] = None,
        exercise_calorie_goal: Optional[int] = None,
        exercise_time_goal: Optional[int] = None,
    ) -> dict:
        now = _utc_now_iso()
        current = self.get_health_goals(user_id)
        cg = calorie_goal if calorie_goal is not None else current["calorie_goal"]
        ecg = exercise_calorie_goal if exercise_calorie_goal is not None else current["exercise_calorie_goal"]
        etg = exercise_time_goal if exercise_time_goal is not None else current["exercise_time_goal"]
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_health_goals
                  (user_id, calorie_goal, exercise_calorie_goal, exercise_time_goal, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    calorie_goal = excluded.calorie_goal,
                    exercise_calorie_goal = excluded.exercise_calorie_goal,
                    exercise_time_goal = excluded.exercise_time_goal,
                    updated_at = excluded.updated_at
                """,
                (user_id, cg, ecg, etg, now),
            )
        return {"calorie_goal": cg, "exercise_calorie_goal": ecg, "exercise_time_goal": etg}
