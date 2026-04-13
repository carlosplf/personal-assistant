"""Dedicated financial data store with Fernet encryption at rest.

Tables: financial_expenses, financial_bills, financial_income.
Sensitive fields (name, amount, category, description, etc.) are encrypted
using a Fernet key derived from CREDENTIAL_ENCRYPTION_KEY.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import threading
import uuid
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


class FinanceStore:
    """Thread-safe SQLite store for expenses, bills and income with Fernet encryption."""

    _ENCRYPTED_EXPENSE_FIELDS = ("name", "amount", "category", "description")
    _ENCRYPTED_BILL_FIELDS = ("bill_name", "budget", "paid_amount", "category")
    _ENCRYPTED_INCOME_FIELDS = ("name", "amount", "category")

    def __init__(
        self,
        db_path: Optional[str] = None,
        encryption_key: Optional[str] = None,
    ):
        if db_path is None:
            db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "assistant_memory.sqlite3")
            )
        self._db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        directory = os.path.dirname(self._db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        raw_key = encryption_key or os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
        if not raw_key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY is required for FinanceStore. "
                "Generate one with: python -c "
                '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        self._ensure_schema()
        self._migrate_encrypt_plaintext_data()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()

    def _is_encrypted(self, value) -> bool:
        """Heuristic: Fernet tokens are base64 and start with 'gAAAAA'."""
        if not isinstance(value, str):
            return False
        return value.startswith("gAAAAA") and len(value) > 50

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_expenses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Outros',
                    description TEXT NOT NULL DEFAULT '',
                    date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_expenses_user_date
                    ON financial_expenses (user_id, date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_bills (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    bill_name TEXT NOT NULL,
                    budget TEXT NOT NULL,
                    paid_amount TEXT NOT NULL DEFAULT '0',
                    paid INTEGER NOT NULL DEFAULT 0,
                    category TEXT NOT NULL DEFAULT 'Outros',
                    due_day INTEGER,
                    reference_month TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_bills_user_month
                    ON financial_bills (user_id, reference_month)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_bills_user_paid
                    ON financial_bills (user_id, paid, reference_month)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_income (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Outros',
                    date TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_financial_income_user_date
                    ON financial_income (user_id, date)
            """)
            conn.commit()

        # Migration: due_date TEXT → due_day INTEGER
        self._migrate_due_date_to_due_day()

    # ------------------------------------------------------------------
    # Migration: due_date TEXT → due_day INTEGER
    # ------------------------------------------------------------------

    def _migrate_due_date_to_due_day(self) -> None:
        """Add due_day column and convert existing due_date values."""
        with self._lock, self._connect() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(financial_bills)").fetchall()]
            if "due_day" not in cols:
                conn.execute("ALTER TABLE financial_bills ADD COLUMN due_day INTEGER")
            if "due_date" in cols:
                rows = conn.execute(
                    "SELECT id, due_date FROM financial_bills WHERE due_date IS NOT NULL AND due_date != ''"
                ).fetchall()
                for row in rows:
                    try:
                        day = int(row[1].split("-")[2]) if "-" in row[1] else int(row[1])
                    except (ValueError, IndexError):
                        day = None
                    if day is not None:
                        conn.execute(
                            "UPDATE financial_bills SET due_day = ? WHERE id = ?",
                            (day, row[0]),
                        )
                conn.commit()

    # ------------------------------------------------------------------
    # Migration: encrypt existing plaintext data
    # ------------------------------------------------------------------

    def _migrate_encrypt_plaintext_data(self) -> None:
        """Encrypt any rows that still have plaintext sensitive fields."""
        with self._lock, self._connect() as conn:
            self._migrate_table(conn, "financial_expenses", "name", self._ENCRYPTED_EXPENSE_FIELDS)
            self._migrate_table(conn, "financial_bills", "bill_name", self._ENCRYPTED_BILL_FIELDS)
            self._migrate_table(conn, "financial_income", "name", self._ENCRYPTED_INCOME_FIELDS)
            conn.commit()

    def _migrate_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        probe_field: str,
        encrypted_fields: tuple[str, ...],
    ) -> None:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            r = dict(row)
            if self._is_encrypted(r.get(probe_field, "")):
                continue
            updates = []
            params: list = []
            for field in encrypted_fields:
                val = str(r.get(field, ""))
                updates.append(f"{field} = ?")
                params.append(self._encrypt(val))
            params.append(r["id"])
            conn.execute(
                f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?",
                params,
            )

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def create_expense(
        self,
        user_id: str,
        name: str,
        amount: float,
        category: str = "Outros",
        description: str = "",
        date: Optional[str] = None,
    ) -> dict:
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        expense_id = uuid.uuid4().hex
        now = _utc_now_iso()
        expense_date = date or datetime.date.today().isoformat()
        cat = category or "Outros"
        desc = description or ""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO financial_expenses
                  (id, user_id, name, amount, category, description, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense_id, user_id,
                    self._encrypt(name.strip()),
                    self._encrypt(str(amount)),
                    self._encrypt(cat),
                    self._encrypt(desc),
                    expense_date, now,
                ),
            )
        return {
            "id": expense_id,
            "name": name.strip(),
            "amount": amount,
            "category": cat,
            "description": desc,
            "date": expense_date,
        }

    def list_expenses_by_date_range(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM financial_expenses
                WHERE user_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
                """,
                (user_id, start_date[:10], end_date[:10]),
            ).fetchall()
        return [self._expense_row_to_dict(r) for r in rows]

    def list_expenses_by_month(self, user_id: str, month: str) -> list[dict]:
        """List expenses for a YYYY-MM month."""
        start = month[:7] + "-01"
        end = month[:7] + "-31"
        return self.list_expenses_by_date_range(user_id, start, end)

    def update_expense(self, user_id: str, expense_id: str, **kwargs) -> dict:
        updates = []
        params: list = []
        for col in ("name", "category", "description", "date"):
            if col in kwargs:
                val = str(kwargs[col]).strip()
                if col == "name" and not val:
                    raise ValueError("name cannot be empty")
                if col == "date":
                    updates.append(f"{col} = ?")
                    params.append(val)
                else:
                    updates.append(f"{col} = ?")
                    params.append(self._encrypt(val))
        if "amount" in kwargs:
            amt = float(kwargs["amount"])
            if amt <= 0:
                raise ValueError("amount must be greater than zero")
            updates.append("amount = ?")
            params.append(self._encrypt(str(amt)))
        if not updates:
            raise ValueError("At least one field to update is required")
        params.extend([expense_id, user_id])
        sql = f"UPDATE financial_expenses SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Expense {expense_id!r} not found")
            row = conn.execute(
                "SELECT * FROM financial_expenses WHERE id = ?", (expense_id,)
            ).fetchone()
        return self._expense_row_to_dict(row)

    def delete_expense(self, user_id: str, expense_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM financial_expenses WHERE id = ? AND user_id = ?",
                (expense_id, user_id),
            )
        return cursor.rowcount > 0

    def _expense_row_to_dict(self, row) -> dict:
        r = dict(row)
        return {
            "id": r["id"],
            "name": self._safe_decrypt(r["name"]),
            "amount": float(self._safe_decrypt(r["amount"])),
            "category": self._safe_decrypt(r.get("category", "Outros")),
            "description": self._safe_decrypt(r.get("description", "")),
            "date": r["date"],
        }

    # ------------------------------------------------------------------
    # Bills
    # ------------------------------------------------------------------

    def create_bill(
        self,
        user_id: str,
        bill_name: str,
        budget: float,
        category: str = "Outros",
        due_day: Optional[int] = None,
        reference_month: Optional[str] = None,
    ) -> dict:
        if budget <= 0:
            raise ValueError("budget must be greater than zero")
        if due_day is not None and not (1 <= due_day <= 31):
            raise ValueError("due_day must be between 1 and 31")
        bill_id = uuid.uuid4().hex
        now = _utc_now_iso()
        if reference_month is None:
            reference_month = datetime.date.today().strftime("%Y-%m")
        cat = category or "Outros"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO financial_bills
                  (id, user_id, bill_name, budget, paid_amount, paid, category,
                   due_day, reference_month, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (
                    bill_id, user_id,
                    self._encrypt(bill_name.strip()),
                    self._encrypt(str(budget)),
                    self._encrypt("0"),
                    self._encrypt(cat),
                    due_day, reference_month, now, now,
                ),
            )
        return {
            "id": bill_id,
            "bill_name": bill_name.strip(),
            "budget": budget,
            "paid_amount": 0.0,
            "paid": False,
            "category": cat,
            "due_day": due_day,
            "reference_month": reference_month,
        }

    def list_bills_by_month(
        self,
        user_id: str,
        reference_month: str,
        unpaid_only: bool = False,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            if unpaid_only:
                rows = conn.execute(
                    """
                    SELECT * FROM financial_bills
                    WHERE user_id = ? AND reference_month = ? AND paid = 0
                    ORDER BY due_day ASC, created_at ASC
                    """,
                    (user_id, reference_month),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM financial_bills
                    WHERE user_id = ? AND reference_month = ?
                    ORDER BY due_day ASC, created_at ASC
                    """,
                    (user_id, reference_month),
                ).fetchall()
        return [self._bill_row_to_dict(r) for r in rows]

    def update_bill_payment(
        self,
        user_id: str,
        bill_id: str,
        paid: bool,
        paid_amount: Optional[float] = None,
    ) -> dict:
        now = _utc_now_iso()
        updates = ["paid = ?", "updated_at = ?"]
        params: list = [1 if paid else 0, now]
        if paid_amount is not None:
            updates.append("paid_amount = ?")
            params.append(self._encrypt(str(float(paid_amount))))
        params.extend([bill_id, user_id])
        sql = f"UPDATE financial_bills SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Bill {bill_id!r} not found")
            row = conn.execute(
                "SELECT * FROM financial_bills WHERE id = ?", (bill_id,)
            ).fetchone()
        return self._bill_row_to_dict(row)

    def update_bill(self, user_id: str, bill_id: str, **kwargs) -> dict:
        now = _utc_now_iso()
        updates = ["updated_at = ?"]
        params: list = [now]
        for col in ("bill_name", "category"):
            if col in kwargs:
                val = str(kwargs[col]).strip() if kwargs[col] is not None else None
                if col == "bill_name" and not val:
                    raise ValueError("bill_name cannot be empty")
                updates.append(f"{col} = ?")
                params.append(self._encrypt(val) if val else self._encrypt(""))
        if "reference_month" in kwargs:
            val = str(kwargs["reference_month"]).strip() if kwargs["reference_month"] is not None else None
            updates.append("reference_month = ?")
            params.append(val)
        if "due_day" in kwargs:
            day = kwargs["due_day"]
            if day is not None:
                day = int(day)
                if not (1 <= day <= 31):
                    raise ValueError("due_day must be between 1 and 31")
            updates.append("due_day = ?")
            params.append(day)
        if "budget" in kwargs:
            b = float(kwargs["budget"])
            if b <= 0:
                raise ValueError("budget must be greater than zero")
            updates.append("budget = ?")
            params.append(self._encrypt(str(b)))
        if "paid" in kwargs:
            updates.append("paid = ?")
            params.append(1 if kwargs["paid"] else 0)
        if "paid_amount" in kwargs:
            updates.append("paid_amount = ?")
            params.append(self._encrypt(str(float(kwargs["paid_amount"]))))
        params.extend([bill_id, user_id])
        sql = f"UPDATE financial_bills SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount == 0:
                raise ValueError(f"Bill {bill_id!r} not found")
            row = conn.execute(
                "SELECT * FROM financial_bills WHERE id = ?", (bill_id,)
            ).fetchone()
        return self._bill_row_to_dict(row)

    def delete_bill(self, user_id: str, bill_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM financial_bills WHERE id = ? AND user_id = ?",
                (bill_id, user_id),
            )
        return cursor.rowcount > 0

    def _bill_row_to_dict(self, row) -> dict:
        r = dict(row)
        return {
            "id": r["id"],
            "bill_name": self._safe_decrypt(r["bill_name"]),
            "budget": float(self._safe_decrypt(r["budget"])),
            "paid_amount": float(self._safe_decrypt(r.get("paid_amount", "0"))),
            "paid": bool(r.get("paid", 0)),
            "category": self._safe_decrypt(r.get("category", "Outros")),
            "due_day": r.get("due_day"),
            "reference_month": r["reference_month"],
        }

    # ------------------------------------------------------------------
    # Income
    # ------------------------------------------------------------------

    def create_income(
        self,
        user_id: str,
        name: str,
        amount: float,
        category: str = "Outros",
        date: Optional[str] = None,
    ) -> dict:
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        income_id = uuid.uuid4().hex
        now = _utc_now_iso()
        income_date = date or datetime.date.today().isoformat()
        cat = category or "Outros"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO financial_income
                  (id, user_id, name, amount, category, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    income_id, user_id,
                    self._encrypt(name.strip()),
                    self._encrypt(str(amount)),
                    self._encrypt(cat),
                    income_date, now,
                ),
            )
        return {
            "id": income_id,
            "name": name.strip(),
            "amount": amount,
            "category": cat,
            "date": income_date,
        }

    def list_income_by_month(self, user_id: str, month: str) -> list[dict]:
        start = month[:7] + "-01"
        end = month[:7] + "-31"
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM financial_income
                WHERE user_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
                """,
                (user_id, start, end),
            ).fetchall()
        return [self._income_row_to_dict(r) for r in rows]

    def delete_income(self, user_id: str, income_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM financial_income WHERE id = ? AND user_id = ?",
                (income_id, user_id),
            )
        return cursor.rowcount > 0

    def _income_row_to_dict(self, row) -> dict:
        r = dict(row)
        return {
            "id": r["id"],
            "name": self._safe_decrypt(r["name"]),
            "amount": float(self._safe_decrypt(r["amount"])),
            "category": self._safe_decrypt(r.get("category", "Outros")),
            "date": r["date"],
        }

    # ------------------------------------------------------------------
    # Decryption helper
    # ------------------------------------------------------------------

    def _safe_decrypt(self, value) -> str:
        """Decrypt a value, returning the raw value if decryption fails."""
        if value is None:
            return ""
        val_str = str(value)
        if not self._is_encrypted(val_str):
            return val_str
        try:
            return self._fernet.decrypt(val_str.encode()).decode()
        except (InvalidToken, Exception):
            return val_str
