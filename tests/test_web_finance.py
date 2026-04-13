"""Tests for finance (expenses + bills) endpoints in web_app.app."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

_ORIGINAL_HTTPX_REQUEST = httpx.Client.request


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch, tmp_path):
    """Set up test environment and reset singletons."""
    db_path = str(tmp_path / "test_finance.sqlite3")

    monkeypatch.setenv("WEB_JWT_SECRET", "test-secret-for-finance-tests")
    monkeypatch.setenv("WEB_JWT_EXPIRY_HOURS", "1")
    monkeypatch.setenv("ASSISTANT_MEMORY_PATH", db_path)
    monkeypatch.setenv("OPENAI_KEY", "test-key")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "_mtPmvrlH22JoC3o3KLUObMoMqYxlXs7aeaNO4kHdoE=")
    monkeypatch.setenv("GOOGLE_OAUTH_CALLBACK_URL", "")

    import web_app.dependencies as deps
    deps._user_store = None
    deps._assistant_service = None
    deps._google_oauth = None
    deps._credential_store = None
    deps._health_store = None
    deps._finance_store = None

    monkeypatch.setattr(httpx.Client, "request", _ORIGINAL_HTTPX_REQUEST)


@pytest.fixture
def client():
    from web_app.app import app
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    from web_app.dependencies import get_user_store
    store = get_user_store()
    store.create_user("financeuser", "testpass123", display_name="Finance User")
    res = client.post("/api/auth/login", json={"username": "financeuser", "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["token"]


@pytest.fixture
def other_token(client):
    from web_app.dependencies import get_user_store
    store = get_user_store()
    store.create_user("otheruser", "testpass456", display_name="Other User")
    res = client.post("/api/auth/login", json={"username": "otheruser", "password": "testpass456"})
    assert res.status_code == 200
    return res.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Auth tests ----

class TestFinanceRequiresAuth:
    def test_dashboard_401(self, client):
        res = client.get("/api/finance/dashboard")
        assert res.status_code in (401, 403)

    def test_create_expense_401(self, client):
        res = client.post("/api/finance/expenses", json={"name": "x", "amount": 10})
        assert res.status_code in (401, 403)

    def test_delete_expense_401(self, client):
        res = client.delete("/api/finance/expenses/some-id")
        assert res.status_code in (401, 403)

    def test_create_bill_401(self, client):
        res = client.post("/api/finance/bills", json={"bill_name": "x", "budget": 100})
        assert res.status_code in (401, 403)

    def test_update_bill_401(self, client):
        res = client.patch("/api/finance/bills/some-id", json={"paid": True})
        assert res.status_code in (401, 403)

    def test_delete_bill_401(self, client):
        res = client.delete("/api/finance/bills/some-id")
        assert res.status_code in (401, 403)


# ---- Dashboard tests ----

class TestFinanceDashboard:
    def test_empty_dashboard(self, client, auth_token):
        res = client.get("/api/finance/dashboard?month=2026-04", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["month"] == "2026-04"
        assert data["expenses"] == []
        assert data["bills"] == []
        assert data["totals"]["total_expenses"] == 0
        assert data["totals"]["total_budget"] == 0
        assert data["category_breakdown"] == []

    def test_dashboard_with_data(self, client, auth_token):
        h = _auth(auth_token)
        client.post("/api/finance/expenses", json={"name": "Uber", "amount": 25.0, "category": "Transporte", "date": "2026-04-05"}, headers=h)
        client.post("/api/finance/expenses", json={"name": "Mercado", "amount": 150.0, "category": "Alimentação", "date": "2026-04-06"}, headers=h)
        client.post("/api/finance/bills", json={"bill_name": "Aluguel", "budget": 1500.0, "reference_month": "2026-04"}, headers=h)

        res = client.get("/api/finance/dashboard?month=2026-04", headers=h)
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_expenses"] == 175.0
        assert data["totals"]["total_budget"] == 1500.0
        assert len(data["expenses"]) == 2
        assert len(data["bills"]) == 1
        assert len(data["category_breakdown"]) == 2

    def test_dashboard_defaults_to_current_month(self, client, auth_token):
        res = client.get("/api/finance/dashboard", headers=_auth(auth_token))
        assert res.status_code == 200
        assert "month" in res.json()

    def test_dashboard_invalid_month(self, client, auth_token):
        res = client.get("/api/finance/dashboard?month=bad", headers=_auth(auth_token))
        assert res.status_code == 400


# ---- Expense CRUD ----

class TestCreateExpense:
    def test_create_expense_success(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "Supermercado", "amount": 250.50, "category": "Alimentação", "date": "2026-04-06"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["expense"]["name"] == "Supermercado"
        assert data["expense"]["amount"] == 250.50
        assert "id" in data["expense"]

    def test_create_expense_minimal(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "Café", "amount": 5.0},
            headers=_auth(auth_token),
        )
        assert res.status_code == 200
        assert res.json()["expense"]["category"] == "Outros"

    def test_create_expense_empty_name(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "", "amount": 10},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_expense_negative_amount(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "Bad", "amount": -5},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_expense_invalid_date(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "X", "amount": 10, "date": "not-a-date"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_expense_name_too_long(self, client, auth_token):
        res = client.post(
            "/api/finance/expenses",
            json={"name": "A" * 201, "amount": 10},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400


class TestDeleteExpense:
    def test_delete_expense_success(self, client, auth_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/expenses", json={"name": "ToDelete", "amount": 10}, headers=h)
        eid = create.json()["expense"]["id"]
        res = client.delete(f"/api/finance/expenses/{eid}", headers=h)
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

    def test_delete_expense_not_found(self, client, auth_token):
        res = client.delete("/api/finance/expenses/nonexistent", headers=_auth(auth_token))
        assert res.status_code == 404

    def test_delete_expense_wrong_user(self, client, auth_token, other_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/expenses", json={"name": "Mine", "amount": 10}, headers=h)
        eid = create.json()["expense"]["id"]
        res = client.delete(f"/api/finance/expenses/{eid}", headers=_auth(other_token))
        assert res.status_code == 404


# ---- Bill CRUD ----

class TestCreateBill:
    def test_create_bill_success(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "Aluguel", "budget": 1500.0, "category": "Moradia", "due_day": 10, "reference_month": "2026-04"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["bill"]["bill_name"] == "Aluguel"
        assert data["bill"]["paid"] is False
        assert data["bill"]["due_day"] == 10

    def test_create_bill_minimal(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "Internet", "budget": 100.0},
            headers=_auth(auth_token),
        )
        assert res.status_code == 200
        assert res.json()["bill"]["category"] == "Outros"
        assert res.json()["bill"]["due_day"] is None

    def test_create_bill_empty_name(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "", "budget": 100},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_bill_negative_budget(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "Bad", "budget": -50},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_bill_invalid_due_day(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "X", "budget": 100, "due_day": 0},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400
        res2 = client.post(
            "/api/finance/bills",
            json={"bill_name": "X", "budget": 100, "due_day": 32},
            headers=_auth(auth_token),
        )
        assert res2.status_code == 400

    def test_create_bill_invalid_reference_month(self, client, auth_token):
        res = client.post(
            "/api/finance/bills",
            json={"bill_name": "X", "budget": 100, "reference_month": "2026"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400


class TestUpdateBill:
    def test_mark_paid(self, client, auth_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/bills", json={"bill_name": "Agua", "budget": 80, "reference_month": "2026-04"}, headers=h)
        bid = create.json()["bill"]["id"]
        res = client.patch(f"/api/finance/bills/{bid}", json={"paid": True, "paid_amount": 78.50}, headers=h)
        assert res.status_code == 200
        assert res.json()["paid"] is True
        assert res.json()["paid_amount"] == 78.50

    def test_mark_unpaid(self, client, auth_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/bills", json={"bill_name": "Luz", "budget": 120, "reference_month": "2026-04"}, headers=h)
        bid = create.json()["bill"]["id"]
        client.patch(f"/api/finance/bills/{bid}", json={"paid": True, "paid_amount": 120}, headers=h)
        res = client.patch(f"/api/finance/bills/{bid}", json={"paid": False}, headers=h)
        assert res.status_code == 200
        assert res.json()["paid"] is False

    def test_update_not_found(self, client, auth_token):
        res = client.patch("/api/finance/bills/nonexistent", json={"paid": True}, headers=_auth(auth_token))
        assert res.status_code == 404

    def test_update_no_fields(self, client, auth_token):
        res = client.patch("/api/finance/bills/some-id", json={}, headers=_auth(auth_token))
        assert res.status_code == 400


class TestDeleteBill:
    def test_delete_bill_success(self, client, auth_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/bills", json={"bill_name": "ToDelete", "budget": 50, "reference_month": "2026-04"}, headers=h)
        bid = create.json()["bill"]["id"]
        res = client.delete(f"/api/finance/bills/{bid}", headers=h)
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

    def test_delete_bill_not_found(self, client, auth_token):
        res = client.delete("/api/finance/bills/nonexistent", headers=_auth(auth_token))
        assert res.status_code == 404

    def test_delete_bill_wrong_user(self, client, auth_token, other_token):
        h = _auth(auth_token)
        create = client.post("/api/finance/bills", json={"bill_name": "Mine", "budget": 100, "reference_month": "2026-04"}, headers=h)
        bid = create.json()["bill"]["id"]
        res = client.delete(f"/api/finance/bills/{bid}", headers=_auth(other_token))
        assert res.status_code == 404


# ---- User isolation ----

class TestFinanceUserIsolation:
    def test_expenses_isolated(self, client, auth_token, other_token):
        h1 = _auth(auth_token)
        h2 = _auth(other_token)
        client.post("/api/finance/expenses", json={"name": "User1 Expense", "amount": 100, "date": "2026-04-01"}, headers=h1)
        res = client.get("/api/finance/dashboard?month=2026-04", headers=h2)
        assert res.status_code == 200
        assert res.json()["expenses"] == []

    def test_bills_isolated(self, client, auth_token, other_token):
        h1 = _auth(auth_token)
        h2 = _auth(other_token)
        client.post("/api/finance/bills", json={"bill_name": "User1 Bill", "budget": 500, "reference_month": "2026-04"}, headers=h1)
        res = client.get("/api/finance/dashboard?month=2026-04", headers=h2)
        assert res.status_code == 200
        assert res.json()["bills"] == []


# ---------------------------------------------------------------------------
# Income Endpoints
# ---------------------------------------------------------------------------

class TestIncomeEndpoints:
    def test_create_income(self, client, auth_token):
        res = client.post(
            "/api/finance/income",
            json={"name": "Salário mensal", "amount": 8000.0, "category": "Salário", "date": "2026-04-05"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["income"]["name"] == "Salário mensal"
        assert data["income"]["amount"] == 8000.0
        assert data["income"]["category"] == "Salário"

    def test_create_income_no_auth(self, client):
        res = client.post("/api/finance/income", json={"name": "Test", "amount": 100})
        assert res.status_code in (401, 403)

    def test_create_income_invalid_amount(self, client, auth_token):
        res = client.post(
            "/api/finance/income",
            json={"name": "Bad", "amount": -10, "date": "2026-04-01"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_create_income_empty_name(self, client, auth_token):
        res = client.post(
            "/api/finance/income",
            json={"name": "", "amount": 100, "date": "2026-04-01"},
            headers=_auth(auth_token),
        )
        assert res.status_code == 400

    def test_delete_income(self, client, auth_token):
        h = _auth(auth_token)
        res = client.post(
            "/api/finance/income",
            json={"name": "Freelance", "amount": 2000, "date": "2026-04-10"},
            headers=h,
        )
        income_id = res.json()["income"]["id"]
        del_res = client.delete(f"/api/finance/income/{income_id}", headers=h)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

    def test_delete_income_not_found(self, client, auth_token):
        res = client.delete("/api/finance/income/nonexistent", headers=_auth(auth_token))
        assert res.status_code == 404

    def test_income_in_dashboard(self, client, auth_token):
        h = _auth(auth_token)
        client.post(
            "/api/finance/income",
            json={"name": "Salário", "amount": 5000, "category": "Salário", "date": "2026-05-01"},
            headers=h,
        )
        client.post(
            "/api/finance/expenses",
            json={"name": "Mercado", "amount": 300, "date": "2026-05-02"},
            headers=h,
        )
        res = client.get("/api/finance/dashboard?month=2026-05", headers=h)
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["total_income"] == 5000
        assert data["totals"]["total_expenses"] == 300
        assert data["totals"]["balance"] == 5000 - 300
        assert len(data["income"]) == 1

    def test_income_isolated_by_user(self, client, auth_token, other_token):
        h1 = _auth(auth_token)
        h2 = _auth(other_token)
        client.post(
            "/api/finance/income",
            json={"name": "My Income", "amount": 3000, "date": "2026-06-01"},
            headers=h1,
        )
        res = client.get("/api/finance/dashboard?month=2026-06", headers=h2)
        assert res.status_code == 200
        assert res.json()["income"] == []
        assert res.json()["totals"]["total_income"] == 0


# ---------------------------------------------------------------------------
# Encryption at Rest
# ---------------------------------------------------------------------------

class TestEncryptionAtRest:
    def test_expense_data_encrypted_in_db(self, client, auth_token):
        """Verify that sensitive expense fields are encrypted in SQLite."""
        import sqlite3
        h = _auth(auth_token)
        client.post(
            "/api/finance/expenses",
            json={"name": "Secret Expense", "amount": 42.50, "category": "Lazer", "date": "2026-07-01"},
            headers=h,
        )
        # Read raw from DB
        from web_app.dependencies import get_finance_store
        store = get_finance_store()
        conn = store._connect()
        try:
            row = conn.execute("SELECT name, amount, category FROM financial_expenses LIMIT 1").fetchone()
        finally:
            conn.close()
        assert row is not None
        # Encrypted fields should NOT contain the plaintext values
        assert row["name"] != "Secret Expense"
        assert row["amount"] != "42.50" and row["amount"] != "42.5"
        assert row["category"] != "Lazer"
        # Encrypted values start with gAAAAA (Fernet token prefix)
        assert str(row["name"]).startswith("gAAAAA")

    def test_income_data_encrypted_in_db(self, client, auth_token):
        """Verify that sensitive income fields are encrypted in SQLite."""
        h = _auth(auth_token)
        client.post(
            "/api/finance/income",
            json={"name": "Secret Income", "amount": 9999, "category": "Salário", "date": "2026-07-01"},
            headers=h,
        )
        from web_app.dependencies import get_finance_store
        store = get_finance_store()
        conn = store._connect()
        try:
            row = conn.execute("SELECT name, amount, category FROM financial_income LIMIT 1").fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["name"] != "Secret Income"
        assert str(row["name"]).startswith("gAAAAA")
