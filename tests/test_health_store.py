"""Unit tests for assistant_connector.health_store.HealthStore."""
from __future__ import annotations

import pytest
from assistant_connector.health_store import (
    HealthStore,
    parse_quantity_details,
    normalize_quantity,
)


@pytest.fixture
def store(tmp_path):
    return HealthStore(db_path=str(tmp_path / "test_health.sqlite3"))


USER = "web:testuser"
OTHER_USER = "web:otheruser"


# ---- Quantity helpers ----

class TestParseQuantityDetails:
    def test_simple_grams(self):
        r = parse_quantity_details("150 g")
        assert r["amount"] == 150.0
        assert r["unit"] == "g"

    def test_ml(self):
        r = parse_quantity_details("250 ml")
        assert r["unit"] == "ml"

    def test_no_numeric_raises(self):
        with pytest.raises(ValueError, match="numeric"):
            parse_quantity_details("abc")

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            parse_quantity_details("0 g")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_quantity_details("")


class TestNormalizeQuantity:
    def test_kg_to_g(self):
        r = normalize_quantity({"amount": 1.0, "unit": "kg"})
        assert r["amount"] == 1000.0
        assert r["unit"] == "g"

    def test_litre_to_ml(self):
        r = normalize_quantity({"amount": 0.5, "unit": "l"})
        assert r["amount"] == 500.0
        assert r["unit"] == "ml"

    def test_grams_unchanged(self):
        r = normalize_quantity({"amount": 200.0, "unit": "g"})
        assert r["amount"] == 200.0
        assert r["unit"] == "g"


# ---- Tasks ----

class TestTasks:
    def test_create_task(self, store):
        task = store.create_task(user_id=USER, task_name="Buy groceries")
        assert task["name"] == "Buy groceries"
        assert task["done"] is False
        assert "id" in task

    def test_list_tasks_empty(self, store):
        assert store.list_tasks(user_id=USER) == []

    def test_list_tasks_returns_own_tasks(self, store):
        store.create_task(user_id=USER, task_name="Task A")
        store.create_task(user_id=OTHER_USER, task_name="Task B")
        tasks = store.list_tasks(user_id=USER)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Task A"

    def test_list_tasks_with_project(self, store):
        store.create_task(user_id=USER, task_name="Work task", project="Work")
        tasks = store.list_tasks(user_id=USER)
        assert tasks[0]["project"] == "Work"

    def test_update_task_done(self, store):
        task = store.create_task(user_id=USER, task_name="Finish report")
        updated = store.update_task(user_id=USER, task_id=task["id"], done=True)
        assert updated["done"] is True

    def test_update_task_name(self, store):
        task = store.create_task(user_id=USER, task_name="Old name")
        updated = store.update_task(user_id=USER, task_id=task["id"], task_name="New name")
        assert updated["name"] == "New name"

    def test_update_task_not_found(self, store):
        with pytest.raises(ValueError):
            store.update_task(user_id=USER, task_id="nonexistent", done=True)

    def test_get_task(self, store):
        task = store.create_task(user_id=USER, task_name="Get me")
        found = store.get_task(user_id=USER, task_id=task["id"])
        assert found is not None
        assert found["name"] == "Get me"

    def test_get_task_wrong_user(self, store):
        task = store.create_task(user_id=USER, task_name="Private")
        found = store.get_task(user_id=OTHER_USER, task_id=task["id"])
        assert found is None

    def test_list_tasks_excludes_done_by_default(self, store):
        task = store.create_task(user_id=USER, task_name="Done task")
        store.update_task(user_id=USER, task_id=task["id"], done=True)
        pending = store.list_tasks(user_id=USER)
        assert all(not t["done"] for t in pending)


# ---- Meals ----

class TestMeals:
    def test_create_meal(self, store):
        meal = store.create_meal(
            user_id=USER, food="Arroz", meal_type="ALMOÇO",
            quantity="200 g", calories=300.0, date="2025-06-01",
        )
        assert meal["food"] == "Arroz"
        assert meal["calories"] == 300.0
        assert "id" in meal

    def test_list_meals_by_date(self, store):
        store.create_meal(user_id=USER, food="Feijão", meal_type="ALMOÇO", quantity="150g", calories=200, date="2025-06-01")
        store.create_meal(user_id=USER, food="Banana", meal_type="LANCHE", quantity="1 un", calories=90, date="2025-06-02")
        meals = store.list_meals_by_date_range(user_id=USER, start_date="2025-06-01", end_date="2025-06-01")
        assert len(meals) == 1
        assert meals[0]["food"] == "Feijão"

    def test_meals_isolated_by_user(self, store):
        store.create_meal(user_id=USER, food="Rice", meal_type="ALMOÇO", quantity="100g", calories=150, date="2025-06-01")
        meals = store.list_meals_by_date_range(user_id=OTHER_USER, start_date="2025-06-01", end_date="2025-06-01")
        assert meals == []

    def test_normalized_quantity_stored(self, store):
        meal = store.create_meal(
            user_id=USER, food="Milk", meal_type="CAFÉ DA MANHÃ",
            quantity="1 l", calories=600, date="2025-06-01",
            normalized_amount=1000.0, normalized_unit="ml",
        )
        assert meal["normalized_amount"] == 1000.0
        assert meal["normalized_unit"] == "ml"

    def test_get_distinct_foods_ordered_by_frequency(self, store):
        store.create_meal(user_id=USER, food="Arroz", meal_type="ALMOÇO", quantity="200g", calories=300, date="2025-06-01")
        store.create_meal(user_id=USER, food="Arroz", meal_type="ALMOÇO", quantity="200g", calories=300, date="2025-06-02")
        store.create_meal(user_id=USER, food="Feijão", meal_type="ALMOÇO", quantity="100g", calories=150, date="2025-06-01")
        foods = store.get_distinct_foods(user_id=USER)
        assert foods[0] == "Arroz"
        assert "Feijão" in foods
        assert len(set(foods)) == len(foods)  # no duplicates

    def test_get_distinct_foods_isolated_by_user(self, store):
        store.create_meal(user_id=USER, food="Banana", meal_type="LANCHE", quantity="1 un", calories=90, date="2025-06-01")
        foods = store.get_distinct_foods(user_id=OTHER_USER)
        assert foods == []

    def test_get_distinct_foods_respects_limit(self, store):
        for i in range(5):
            store.create_meal(user_id=USER, food=f"Food{i}", meal_type="ALMOÇO", quantity="100g", calories=100, date="2025-06-01")
        foods = store.get_distinct_foods(user_id=USER, limit=3)
        assert len(foods) == 3


# ---- Exercises ----

class TestExercises:
    def test_create_exercise(self, store):
        ex = store.create_exercise(user_id=USER, activity="Corrida", calories=350, date="2025-06-01")
        assert ex["activity"] == "Corrida"
        assert ex["done"] is True
        assert "id" in ex

    def test_create_exercise_with_effort_level(self, store):
        ex = store.create_exercise(user_id=USER, activity="Musculação", calories=250, date="2025-06-01", effort_level=8)
        assert ex["effort_level"] == 8

    def test_create_exercise_without_effort_level(self, store):
        ex = store.create_exercise(user_id=USER, activity="Corrida", calories=300, date="2025-06-02")
        assert ex["effort_level"] is None

    def test_update_exercise_effort_level(self, store):
        ex = store.create_exercise(user_id=USER, activity="Bike", calories=200, date="2025-06-01")
        updated = store.update_exercise(user_id=USER, exercise_id=ex["id"], effort_level=5)
        assert updated["effort_level"] == 5

    def test_list_exercises_returns_effort_level(self, store):
        store.create_exercise(user_id=USER, activity="Caminhada", calories=150, date="2025-06-01", effort_level=3)
        exs = store.list_exercises_by_date_range(user_id=USER, start_date="2025-06-01", end_date="2025-06-01")
        assert exs[0]["effort_level"] == 3

    def test_update_exercise_done(self, store):
        ex = store.create_exercise(user_id=USER, activity="Yoga", calories=120, date="2025-06-01", done=False)
        updated = store.update_exercise(user_id=USER, exercise_id=ex["id"], done=True)
        assert updated["done"] is True

    def test_update_exercise_not_found(self, store):
        with pytest.raises(ValueError):
            store.update_exercise(user_id=USER, exercise_id="bad-id", done=True)

    def test_list_exercises_by_date(self, store):
        store.create_exercise(user_id=USER, activity="Swim", calories=400, date="2025-06-01")
        store.create_exercise(user_id=USER, activity="Bike", calories=300, date="2025-06-02")
        exs = store.list_exercises_by_date_range(user_id=USER, start_date="2025-06-01", end_date="2025-06-01")
        assert len(exs) == 1
        assert exs[0]["activity"] == "Swim"

    def test_find_duplicate(self, store):
        store.create_exercise(user_id=USER, activity="Musculação", calories=200, date="2025-06-01", done=False)
        dup = store.find_exercise_duplicate(user_id=USER, activity="Musculação", date="2025-06-01")
        assert dup is not None
        assert dup["activity"] == "Musculação"

    def test_no_duplicate_for_different_activity(self, store):
        store.create_exercise(user_id=USER, activity="Musculação", calories=200, date="2025-06-01", done=False)
        dup = store.find_exercise_duplicate(user_id=USER, activity="Corrida", date="2025-06-01")
        assert dup is None


# ---- Expenses ----

class TestExpenses:
    @pytest.fixture
    def fstore(self, tmp_path):
        from assistant_connector.finance_store import FinanceStore
        return FinanceStore(
            db_path=str(tmp_path / "test_finance.sqlite3"),
            encryption_key="_mtPmvrlH22JoC3o3KLUObMoMqYxlXs7aeaNO4kHdoE=",
        )

    def test_create_expense(self, fstore):
        exp = fstore.create_expense(user_id=USER, name="Mercado", amount=150.50, date="2025-06-01")
        assert exp["name"] == "Mercado"
        assert exp["amount"] == 150.50
        assert "id" in exp

    def test_list_expenses_by_date_range(self, fstore):
        fstore.create_expense(user_id=USER, name="Aluguel", amount=1200.0, date="2025-06-01")
        fstore.create_expense(user_id=USER, name="Internet", amount=80.0, date="2025-07-01")
        exps = fstore.list_expenses_by_date_range(user_id=USER, start_date="2025-06-01", end_date="2025-06-30")
        assert len(exps) == 1
        assert exps[0]["name"] == "Aluguel"

    def test_expenses_isolated_by_user(self, fstore):
        fstore.create_expense(user_id=USER, name="Gym", amount=100.0, date="2025-06-01")
        exps = fstore.list_expenses_by_date_range(user_id=OTHER_USER, start_date="2025-06-01", end_date="2025-06-30")
        assert exps == []

    def test_invalid_amount_raises(self, fstore):
        with pytest.raises(ValueError):
            fstore.create_expense(user_id=USER, name="Bad", amount=-50.0, date="2025-06-01")

    def test_delete_expense(self, fstore):
        exp = fstore.create_expense(user_id=USER, name="ToDelete", amount=30.0, date="2025-06-01")
        assert fstore.delete_expense(user_id=USER, expense_id=exp["id"]) is True
        assert fstore.list_expenses_by_date_range(user_id=USER, start_date="2025-06-01", end_date="2025-06-30") == []

    def test_delete_expense_wrong_user(self, fstore):
        exp = fstore.create_expense(user_id=USER, name="Mine", amount=30.0, date="2025-06-01")
        assert fstore.delete_expense(user_id=OTHER_USER, expense_id=exp["id"]) is False

    def test_list_expenses_by_month(self, fstore):
        fstore.create_expense(user_id=USER, name="June", amount=50.0, date="2025-06-15")
        fstore.create_expense(user_id=USER, name="July", amount=60.0, date="2025-07-01")
        exps = fstore.list_expenses_by_month(user_id=USER, month="2025-06")
        assert len(exps) == 1
        assert exps[0]["name"] == "June"


# ---- Bills ----

class TestBills:
    @pytest.fixture
    def fstore(self, tmp_path):
        from assistant_connector.finance_store import FinanceStore
        return FinanceStore(
            db_path=str(tmp_path / "test_finance.sqlite3"),
            encryption_key="_mtPmvrlH22JoC3o3KLUObMoMqYxlXs7aeaNO4kHdoE=",
        )

    def test_create_bill(self, fstore):
        bill = fstore.create_bill(
            user_id=USER, bill_name="Aluguel", budget=1500.0, reference_month="2025-06",
        )
        assert bill["bill_name"] == "Aluguel"
        assert bill["paid"] is False
        assert "id" in bill

    def test_list_bills_by_month(self, fstore):
        fstore.create_bill(user_id=USER, bill_name="Internet", budget=100.0, reference_month="2025-06")
        fstore.create_bill(user_id=USER, bill_name="Streaming", budget=50.0, reference_month="2025-07")
        bills = fstore.list_bills_by_month(user_id=USER, reference_month="2025-06")
        assert len(bills) == 1
        assert bills[0]["bill_name"] == "Internet"

    def test_update_bill_payment(self, fstore):
        bill = fstore.create_bill(user_id=USER, bill_name="Water", budget=80.0, reference_month="2025-06")
        updated = fstore.update_bill_payment(user_id=USER, bill_id=bill["id"], paid=True, paid_amount=80.0)
        assert updated["paid"] is True
        assert updated["paid_amount"] == 80.0

    def test_update_bill_not_found(self, fstore):
        with pytest.raises(ValueError):
            fstore.update_bill_payment(user_id=USER, bill_id="bad-id", paid=True)

    def test_delete_bill(self, fstore):
        bill = fstore.create_bill(user_id=USER, bill_name="OldBill", budget=50.0, reference_month="2025-06")
        assert fstore.delete_bill(user_id=USER, bill_id=bill["id"]) is True
        assert fstore.list_bills_by_month(user_id=USER, reference_month="2025-06") == []

    def test_bills_isolated_by_user(self, fstore):
        fstore.create_bill(user_id=USER, bill_name="Rent", budget=1000.0, reference_month="2025-06")
        bills = fstore.list_bills_by_month(user_id=OTHER_USER, reference_month="2025-06")
        assert bills == []
