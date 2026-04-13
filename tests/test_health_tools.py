"""Unit tests for assistant_connector.tools.health_tools and finance_tools."""
from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch


USER_ID = "web:testuser"


@pytest.fixture(autouse=True)
def _set_db_path(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSISTANT_MEMORY_PATH", str(tmp_path / "tools_test.sqlite3"))
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "_mtPmvrlH22JoC3o3KLUObMoMqYxlXs7aeaNO4kHdoE=")


@pytest.fixture
def ctx():
    c = MagicMock()
    c.user_id = USER_ID
    return c


@pytest.fixture
def fresh_store(tmp_path):
    """Return a fresh HealthStore that the tools module also uses (via monkeypatch)."""
    from assistant_connector.health_store import HealthStore
    db = str(tmp_path / "tools_test.sqlite3")
    store = HealthStore(db_path=db)
    return store


@pytest.fixture
def fresh_finance_store(tmp_path):
    """Return a fresh FinanceStore for finance tool tests."""
    from assistant_connector.finance_store import FinanceStore
    db = str(tmp_path / "tools_test.sqlite3")
    store = FinanceStore(db_path=db, encryption_key="_mtPmvrlH22JoC3o3KLUObMoMqYxlXs7aeaNO4kHdoE=")
    return store


@pytest.fixture(autouse=True)
def patch_store(fresh_store, fresh_finance_store):
    """Patch the module-level singletons so all tools use the tmp store."""
    with patch("assistant_connector.tools.health_tools._health_store", fresh_store), \
         patch("assistant_connector.tools.finance_tools._finance_store", fresh_finance_store):
        yield fresh_store


@pytest.fixture
def fin_store(fresh_finance_store):
    """Expose the FinanceStore for tests that insert/query financial data."""
    return fresh_finance_store


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    def test_empty(self, ctx):
        from assistant_connector.tools.health_tools import list_tasks
        result = list_tasks({}, ctx)
        assert result["total"] == 0
        assert result["tasks"] == []

    def test_with_tasks(self, ctx, patch_store):
        patch_store.create_task(user_id=USER_ID, task_name="Buy groceries")
        from assistant_connector.tools.health_tools import list_tasks
        result = list_tasks({"limit": 10}, ctx)
        assert result["total"] == 1
        assert result["tasks"][0]["name"] == "Buy groceries"


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------

class TestCreateTask:
    def test_create_success(self, ctx):
        from assistant_connector.tools.health_tools import create_task
        result = create_task({"task_name": "Write tests", "project": "Work"}, ctx)
        assert result["name"] == "Write tests"
        assert result["project"] == "Work"

    def test_missing_task_name_raises(self, ctx):
        from assistant_connector.tools.health_tools import create_task
        with pytest.raises(ValueError, match="task_name"):
            create_task({}, ctx)

    def test_invalid_due_date_raises(self, ctx):
        from assistant_connector.tools.health_tools import create_task
        with pytest.raises(ValueError, match="due_date"):
            create_task({"task_name": "Test", "due_date": "not-a-date"}, ctx)


# ---------------------------------------------------------------------------
# edit_task
# ---------------------------------------------------------------------------

class TestEditTask:
    def test_edit_done(self, ctx, patch_store):
        task = patch_store.create_task(user_id=USER_ID, task_name="Finish report")
        from assistant_connector.tools.health_tools import edit_task
        result = edit_task({"task_id": task["id"], "done": True}, ctx)
        assert result["done"] is True

    def test_missing_task_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_task
        with pytest.raises(ValueError, match="task_id"):
            edit_task({"done": True}, ctx)

    def test_no_fields_raises(self, ctx, patch_store):
        task = patch_store.create_task(user_id=USER_ID, task_name="Task")
        from assistant_connector.tools.health_tools import edit_task
        with pytest.raises(ValueError, match="At least one"):
            edit_task({"task_id": task["id"]}, ctx)


# ---------------------------------------------------------------------------
# register_meal
# ---------------------------------------------------------------------------

class TestRegisterMeal:
    def test_register_batch_success(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        result = register_meal({
            "refeicao": "ALMOÇO",
            "alimentos": [
                {"alimento": "Arroz", "quantidade": "200g", "calorias_estimadas": 300},
                {"alimento": "Frango", "quantidade": "150g", "calorias_estimadas": 200},
            ],
        }, ctx)
        assert result["status"] == "created"
        assert len(result["meals"]) == 2
        assert result["total_calories"] == 500.0
        assert result["meal_group_id"]
        assert result["meals"][0]["food"] == "Arroz"
        assert result["meals"][1]["food"] == "Frango"

    def test_register_single_item_batch(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        result = register_meal({
            "refeicao": "JANTAR",
            "alimentos": [{"alimento": "Salada", "quantidade": "100g", "calorias_estimadas": 50}],
        }, ctx)
        assert result["status"] == "created"
        assert len(result["meals"]) == 1
        assert result["meal_group_id"]

    def test_register_legacy_single_food(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        result = register_meal({
            "alimento": "Arroz", "refeicao": "ALMOÇO",
            "quantidade": "200g", "calorias_estimadas": 300,
        }, ctx)
        assert result["status"] == "created"
        assert len(result["meals"]) == 1
        assert result["meals"][0]["food"] == "Arroz"
        assert result["meal_group_id"]

    def test_empty_alimentos_raises(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        with pytest.raises(ValueError):
            register_meal({"refeicao": "ALMOÇO", "alimentos": []}, ctx)

    def test_missing_food_in_item_raises(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        with pytest.raises(ValueError):
            register_meal({"refeicao": "ALMOÇO", "alimentos": [{"quantidade": "100g", "calorias_estimadas": 200}]}, ctx)

    def test_invalid_category_raises(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        with pytest.raises(ValueError):
            register_meal({"refeicao": "INVALID", "alimentos": [{"alimento": "Frango", "quantidade": "100g", "calorias_estimadas": 200}]}, ctx)

    def test_category_alias(self, ctx):
        from assistant_connector.tools.health_tools import register_meal
        result = register_meal({
            "refeicao": "cafe",
            "alimentos": [{"alimento": "Café", "quantidade": "200ml", "calorias_estimadas": 10}],
        }, ctx)
        assert result["meals"][0]["meal_type"] == "CAFÉ DA MANHÃ"

    def test_batch_all_same_group(self, ctx, patch_store):
        from assistant_connector.tools.health_tools import register_meal
        result = register_meal({
            "refeicao": "ALMOÇO",
            "alimentos": [
                {"alimento": "Arroz", "quantidade": "200g", "calorias_estimadas": 300},
                {"alimento": "Feijão", "quantidade": "150g", "calorias_estimadas": 200},
            ],
        }, ctx)
        gid = result["meal_group_id"]
        assert result["meals"][0]["meal_group_id"] == gid
        assert result["meals"][1]["meal_group_id"] == gid


# ---------------------------------------------------------------------------
# analyze_meals
# ---------------------------------------------------------------------------

class TestAnalyzeMeals:
    def test_empty_result(self, ctx):
        from assistant_connector.tools.health_tools import analyze_meals
        result = analyze_meals({"days_back": 7}, ctx)
        assert result["total_entries"] == 0
        assert result["total_calories"] == 0

    def test_with_meals(self, ctx, patch_store):
        patch_store.create_meal(user_id=USER_ID, food="Arroz", meal_type="ALMOÇO",
                                quantity="200g", calories=300, date="2025-06-01")
        patch_store.create_meal(user_id=USER_ID, food="Frango", meal_type="ALMOÇO",
                                quantity="150g", calories=250, date="2025-06-01")
        from assistant_connector.tools.health_tools import analyze_meals
        with patch("assistant_connector.tools.health_tools.today_in_configured_timezone",
                   return_value=__import__("datetime").date(2025, 6, 1)):
            result = analyze_meals({"days_back": 0, "days_forward": 0}, ctx)
        assert result["total_entries"] == 2
        assert result["total_calories"] == 550.0


# ---------------------------------------------------------------------------
# register_exercise
# ---------------------------------------------------------------------------

class TestRegisterExercise:
    def test_register_success(self, ctx):
        from assistant_connector.tools.health_tools import register_exercise
        result = register_exercise({
            "atividade": "Corrida", "calorias": 350
        }, ctx)
        assert result["status"] == "created"
        assert result["exercise"]["activity"] == "Corrida"

    def test_missing_activity_raises(self, ctx):
        from assistant_connector.tools.health_tools import register_exercise
        with pytest.raises(ValueError):
            register_exercise({"calorias": 300}, ctx)

    def test_duplicate_detected(self, ctx, patch_store):
        patch_store.create_exercise(user_id=USER_ID, activity="Musculação",
                                    calories=200, date="2025-06-15", done=False)
        from assistant_connector.tools.health_tools import register_exercise
        with patch("assistant_connector.tools.health_tools.today_iso_in_configured_timezone",
                   return_value="2025-06-15"):
            result = register_exercise({"atividade": "Musculação", "calorias": 200, "data": "2025-06-15"}, ctx)
        assert result.get("error") == "duplicate_exercise_found"


# ---------------------------------------------------------------------------
# edit_exercise
# ---------------------------------------------------------------------------

class TestEditExercise:
    def test_edit_success(self, ctx, patch_store):
        ex = patch_store.create_exercise(user_id=USER_ID, activity="Yoga",
                                         calories=120, date="2025-06-01", done=False)
        from assistant_connector.tools.health_tools import edit_exercise
        result = edit_exercise({"exercise_id": ex["id"], "done": True}, ctx)
        assert result["done"] is True

    def test_missing_exercise_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_exercise
        with pytest.raises(ValueError, match="exercise_id"):
            edit_exercise({"done": True}, ctx)

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_exercise
        with pytest.raises(Exception):
            edit_exercise({"exercise_id": "nonexistent-id", "done": True}, ctx)


# ---------------------------------------------------------------------------
# analyze_exercises
# ---------------------------------------------------------------------------

class TestAnalyzeExercises:
    def test_empty_result(self, ctx):
        from assistant_connector.tools.health_tools import analyze_exercises
        result = analyze_exercises({"days_back": 7}, ctx)
        assert result["total_entries"] == 0

    def test_with_exercises(self, ctx, patch_store):
        patch_store.create_exercise(user_id=USER_ID, activity="Corrida",
                                    calories=350, date="2025-06-01", done=True)
        from assistant_connector.tools.health_tools import analyze_exercises
        with patch("assistant_connector.tools.health_tools.today_in_configured_timezone",
                   return_value=__import__("datetime").date(2025, 6, 1)):
            result = analyze_exercises({"days_back": 0, "days_forward": 0}, ctx)
        assert result["total_entries"] == 1
        assert result["totals"]["total_exercise_calories"] == 350.0


# ---------------------------------------------------------------------------
# check_daily_logging_status
# ---------------------------------------------------------------------------

class TestCheckDailyLoggingStatus:
    def test_nothing_logged(self, ctx):
        from assistant_connector.tools.health_tools import check_daily_logging_status
        result = check_daily_logging_status({}, ctx)
        assert result["meal_count"] == 0
        assert result["exercise_count"] == 0

    def test_meal_logged(self, ctx, patch_store):
        import datetime
        today = datetime.date.today().isoformat()
        patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                quantity="100g", calories=150, date=today)
        from assistant_connector.tools.health_tools import check_daily_logging_status
        result = check_daily_logging_status({}, ctx)
        assert result["meal_count"] == 1


# ---------------------------------------------------------------------------
# Finance tools: register_expense
# ---------------------------------------------------------------------------

class TestRegisterExpense:
    def test_success(self, ctx):
        from assistant_connector.tools.finance_tools import register_expense
        result = register_expense({"description": "Mercado", "amount": 150.0}, ctx)
        assert result["status"] == "created"
        assert result["expense"]["amount"] == 150.0

    def test_infers_category(self, ctx):
        from assistant_connector.tools.finance_tools import register_expense
        result = register_expense({"description": "iFood delivery", "amount": 50.0}, ctx)
        assert result["expense"]["category"] == "Alimentação"

    def test_missing_description_raises(self, ctx):
        from assistant_connector.tools.finance_tools import register_expense
        with pytest.raises(ValueError, match="description"):
            register_expense({"amount": 100}, ctx)

    def test_negative_amount_raises(self, ctx):
        from assistant_connector.tools.finance_tools import register_expense
        with pytest.raises(ValueError, match="greater than zero"):
            register_expense({"description": "Test", "amount": -50}, ctx)


# ---------------------------------------------------------------------------
# Finance tools: analyze_expenses
# ---------------------------------------------------------------------------

class TestAnalyzeExpenses:
    def test_empty_month(self, ctx):
        from assistant_connector.tools.finance_tools import analyze_expenses
        result = analyze_expenses({"month": "2025-06"}, ctx)
        assert result["expenses_count"] == 0
        assert result["total_spent"] == 0.0

    def test_with_expenses(self, ctx, fin_store):
        fin_store.create_expense(user_id=USER_ID, name="Aluguel", amount=1200.0,
                                   category="Moradia", date="2025-06-01")
        fin_store.create_expense(user_id=USER_ID, name="Internet", amount=80.0,
                                   category="Moradia", date="2025-06-10")
        from assistant_connector.tools.finance_tools import analyze_expenses
        result = analyze_expenses({"month": "2025-06"}, ctx)
        assert result["expenses_count"] == 2
        assert result["total_spent"] == 1280.0


# ---------------------------------------------------------------------------
# Finance tools: list_bills
# ---------------------------------------------------------------------------

class TestListBills:
    def test_empty(self, ctx):
        from assistant_connector.tools.finance_tools import list_bills
        result = list_bills({"month": "2025-06"}, ctx)
        assert result["bills"] == []

    def test_with_unpaid_bill(self, ctx, fin_store):
        fin_store.create_bill(user_id=USER_ID, bill_name="Internet",
                                budget=100.0, reference_month="2025-06")
        from assistant_connector.tools.finance_tools import list_bills
        result = list_bills({"month": "2025-06"}, ctx)
        assert len(result["bills"]) == 1
        assert result["bills"][0]["bill_name"] == "Internet"


# ---------------------------------------------------------------------------
# Finance tools: pay_bill
# ---------------------------------------------------------------------------

class TestPayBill:
    def test_pay_success(self, ctx, fin_store):
        bill = fin_store.create_bill(user_id=USER_ID, bill_name="Rent",
                                       budget=1500.0, reference_month="2025-06")
        from assistant_connector.tools.finance_tools import pay_bill
        result = pay_bill({"bill_id": bill["id"], "paid_amount": 1500.0}, ctx)
        assert result["paid"] is True

    def test_missing_bill_id_raises(self, ctx):
        from assistant_connector.tools.finance_tools import pay_bill
        with pytest.raises(ValueError, match="bill_id"):
            pay_bill({}, ctx)


# ---------------------------------------------------------------------------
# Finance tools: analyze_bills
# ---------------------------------------------------------------------------

class TestAnalyzeBills:
    def test_empty_month(self, ctx):
        from assistant_connector.tools.finance_tools import analyze_bills
        result = analyze_bills({"month": "2025-06"}, ctx)
        assert result["total_bills"] == 0

    def test_with_bills(self, ctx, fin_store):
        fin_store.create_bill(user_id=USER_ID, bill_name="Streaming",
                                budget=50.0, reference_month="2025-06")
        from assistant_connector.tools.finance_tools import analyze_bills
        result = analyze_bills({"month": "2025-06"}, ctx)
        assert result["total_bills"] == 1
        assert result["total_budget"] == 50.0


# ---------------------------------------------------------------------------
# LLM calorie inference
# ---------------------------------------------------------------------------

class TestMealCalorieInference:
    def test_infers_when_omitted(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories", return_value=250.0):
            from assistant_connector.tools.health_tools import register_meal
            result = register_meal({
                "refeicao": "ALMOÇO",
                "alimentos": [{"alimento": "Arroz", "quantidade": "200g"}],
            }, ctx)
        assert result["status"] == "created"
        assert result["meals"][0]["calories"] == 250.0
        assert result["meals"][0]["calorie_estimation_method"] == "llm_inferred"

    def test_provided_calories_take_precedence(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories") as mock_est:
            from assistant_connector.tools.health_tools import register_meal
            result = register_meal({
                "refeicao": "ALMOÇO",
                "alimentos": [{"alimento": "Arroz", "quantidade": "200g", "calorias_estimadas": 300}],
            }, ctx)
        mock_est.assert_not_called()
        assert result["meals"][0]["calorie_estimation_method"] == "provided"

    def test_raises_when_inference_fails(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories", return_value=None):
            from assistant_connector.tools.health_tools import register_meal
            with pytest.raises(ValueError, match="LLM estimation also failed"):
                register_meal({
                    "refeicao": "ALMOÇO",
                    "alimentos": [{"alimento": "Arroz", "quantidade": "200g"}],
                }, ctx)

    def test_mixed_inferred_and_provided(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories", return_value=180.0):
            from assistant_connector.tools.health_tools import register_meal
            result = register_meal({
                "refeicao": "ALMOÇO",
                "alimentos": [
                    {"alimento": "Arroz", "quantidade": "200g", "calorias_estimadas": 300},
                    {"alimento": "Salada", "quantidade": "100g"},
                ],
            }, ctx)
        assert result["meals"][0]["calorie_estimation_method"] == "provided"
        assert result["meals"][1]["calorie_estimation_method"] == "llm_inferred"
        assert result["total_calories"] == 480.0


class TestExerciseCalorieInference:
    def test_infers_when_omitted(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories", return_value=400.0):
            from assistant_connector.tools.health_tools import register_exercise
            result = register_exercise({"atividade": "Corrida 30min"}, ctx)
        assert result["status"] == "created"
        assert result["exercise"]["calories"] == 400.0
        assert result["exercise"]["calorie_estimation_method"] == "llm_inferred"

    def test_provided_calories_take_precedence(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories") as mock_est:
            from assistant_connector.tools.health_tools import register_exercise
            result = register_exercise({"atividade": "Corrida", "calorias": 350}, ctx)
        mock_est.assert_not_called()
        assert result["exercise"]["calorie_estimation_method"] == "provided"

    def test_raises_when_inference_fails(self, ctx):
        with patch("assistant_connector.tools.health_tools.estimate_calories", return_value=None):
            from assistant_connector.tools.health_tools import register_exercise
            with pytest.raises(ValueError, match="LLM estimation also failed"):
                register_exercise({"atividade": "Natação"}, ctx)


# ---------------------------------------------------------------------------
# delete_task
# ---------------------------------------------------------------------------

class TestDeleteTask:
    def test_delete_success(self, ctx, patch_store):
        task = patch_store.create_task(user_id=USER_ID, task_name="To remove")
        from assistant_connector.tools.health_tools import delete_task
        result = delete_task({"task_id": task["id"]}, ctx)
        assert result["status"] == "deleted"

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_task
        with pytest.raises(ValueError, match="task_id"):
            delete_task({}, ctx)

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_task
        with pytest.raises(ValueError, match="not found"):
            delete_task({"task_id": "nonexistent"}, ctx)


# ---------------------------------------------------------------------------
# list_meals
# ---------------------------------------------------------------------------

class TestListMeals:
    def test_empty(self, ctx):
        from assistant_connector.tools.health_tools import list_meals
        result = list_meals({}, ctx)
        assert result["total"] == 0
        assert result["meal_groups"] == []
        assert result["ungrouped_items"] == []

    def test_grouped_by_meal_group_id(self, ctx, patch_store):
        gid = "testgroup123"
        patch_store.create_meal(user_id=USER_ID, food="Arroz", meal_type="ALMOÇO",
                                quantity="200g", calories=300, meal_group_id=gid)
        patch_store.create_meal(user_id=USER_ID, food="Frango", meal_type="ALMOÇO",
                                quantity="150g", calories=200, meal_group_id=gid)
        from assistant_connector.tools.health_tools import list_meals
        result = list_meals({"n_days": 1}, ctx)
        assert result["total"] == 2
        assert len(result["meal_groups"]) == 1
        assert result["meal_groups"][0]["meal_group_id"] == gid
        assert len(result["meal_groups"][0]["items"]) == 2
        assert result["meal_groups"][0]["total_calories"] == 500.0
        assert result["ungrouped_items"] == []

    def test_ungrouped_items_separated(self, ctx, patch_store):
        patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                quantity="200g", calories=300)
        from assistant_connector.tools.health_tools import list_meals
        result = list_meals({"n_days": 1}, ctx)
        assert result["total"] >= 1
        assert len(result["ungrouped_items"]) >= 1


# ---------------------------------------------------------------------------
# edit_meal
# ---------------------------------------------------------------------------

class TestEditMeal:
    def test_edit_success(self, ctx, patch_store):
        meal = patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                       quantity="200g", calories=300)
        from assistant_connector.tools.health_tools import edit_meal
        result = edit_meal({"meal_id": meal["id"], "alimento": "Brown Rice"}, ctx)
        assert result["food"] == "Brown Rice"

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_meal
        with pytest.raises(ValueError, match="meal_id"):
            edit_meal({}, ctx)

    def test_no_fields_raises(self, ctx, patch_store):
        meal = patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                       quantity="200g", calories=300)
        from assistant_connector.tools.health_tools import edit_meal
        with pytest.raises(ValueError, match="At least one"):
            edit_meal({"meal_id": meal["id"]}, ctx)


# ---------------------------------------------------------------------------
# delete_meal
# ---------------------------------------------------------------------------

class TestDeleteMeal:
    def test_delete_success(self, ctx, patch_store):
        meal = patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                       quantity="200g", calories=300)
        from assistant_connector.tools.health_tools import delete_meal
        result = delete_meal({"meal_id": meal["id"]}, ctx)
        assert result["status"] == "deleted"

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_meal
        with pytest.raises(ValueError, match="not found"):
            delete_meal({"meal_id": "nonexistent"}, ctx)


# ---------------------------------------------------------------------------
# delete_meal_group
# ---------------------------------------------------------------------------

class TestDeleteMealGroup:
    def test_delete_group_success(self, ctx, patch_store):
        gid = "grp_del_test"
        patch_store.create_meal(user_id=USER_ID, food="Arroz", meal_type="ALMOÇO",
                                quantity="200g", calories=300, meal_group_id=gid)
        patch_store.create_meal(user_id=USER_ID, food="Frango", meal_type="ALMOÇO",
                                quantity="150g", calories=200, meal_group_id=gid)
        from assistant_connector.tools.health_tools import delete_meal_group
        result = delete_meal_group({"meal_group_id": gid}, ctx)
        assert result["status"] == "deleted"
        assert result["items_deleted"] == 2

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_meal_group
        with pytest.raises(ValueError, match="meal_group_id"):
            delete_meal_group({}, ctx)

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_meal_group
        with pytest.raises(ValueError, match="not found"):
            delete_meal_group({"meal_group_id": "nonexistent"}, ctx)


# ---------------------------------------------------------------------------
# edit_meal_group
# ---------------------------------------------------------------------------

class TestEditMealGroup:
    def test_edit_meal_type(self, ctx, patch_store):
        gid = "grp_edit_test"
        patch_store.create_meal(user_id=USER_ID, food="Arroz", meal_type="ALMOÇO",
                                quantity="200g", calories=300, meal_group_id=gid)
        patch_store.create_meal(user_id=USER_ID, food="Feijão", meal_type="ALMOÇO",
                                quantity="100g", calories=150, meal_group_id=gid)
        from assistant_connector.tools.health_tools import edit_meal_group
        result = edit_meal_group({"meal_group_id": gid, "refeicao": "JANTAR"}, ctx)
        assert result["status"] == "updated"
        assert result["items_updated"] == 2

    def test_edit_date(self, ctx, patch_store):
        gid = "grp_edit_date"
        patch_store.create_meal(user_id=USER_ID, food="Arroz", meal_type="ALMOÇO",
                                quantity="200g", calories=300, meal_group_id=gid)
        from assistant_connector.tools.health_tools import edit_meal_group
        result = edit_meal_group({"meal_group_id": gid, "data": "2025-06-15"}, ctx)
        assert result["status"] == "updated"
        assert result["items_updated"] == 1

    def test_no_fields_raises(self, ctx, patch_store):
        gid = "grp_no_fields"
        patch_store.create_meal(user_id=USER_ID, food="Rice", meal_type="ALMOÇO",
                                quantity="200g", calories=300, meal_group_id=gid)
        from assistant_connector.tools.health_tools import edit_meal_group
        with pytest.raises(ValueError, match="At least one"):
            edit_meal_group({"meal_group_id": gid}, ctx)

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_meal_group
        with pytest.raises(ValueError, match="meal_group_id"):
            edit_meal_group({"refeicao": "JANTAR"}, ctx)

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import edit_meal_group
        with pytest.raises(ValueError, match="not found"):
            edit_meal_group({"meal_group_id": "nonexistent", "refeicao": "JANTAR"}, ctx)




class TestListExercises:
    def test_empty(self, ctx):
        from assistant_connector.tools.health_tools import list_exercises
        result = list_exercises({}, ctx)
        assert result["total"] == 0
        assert result["exercises"] == []

    def test_with_data(self, ctx, patch_store):
        patch_store.create_exercise(user_id=USER_ID, activity="Running",
                                     calories=250)
        from assistant_connector.tools.health_tools import list_exercises
        result = list_exercises({"n_days": 1}, ctx)
        assert result["total"] >= 1


# ---------------------------------------------------------------------------
# delete_exercise
# ---------------------------------------------------------------------------

class TestDeleteExercise:
    def test_delete_success(self, ctx, patch_store):
        ex = patch_store.create_exercise(user_id=USER_ID, activity="Running",
                                          calories=250)
        from assistant_connector.tools.health_tools import delete_exercise
        result = delete_exercise({"exercise_id": ex["id"]}, ctx)
        assert result["status"] == "deleted"

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.health_tools import delete_exercise
        with pytest.raises(ValueError, match="not found"):
            delete_exercise({"exercise_id": "nonexistent"}, ctx)


# ---------------------------------------------------------------------------
# list_expenses
# ---------------------------------------------------------------------------

class TestListExpenses:
    def test_empty(self, ctx):
        from assistant_connector.tools.finance_tools import list_expenses
        result = list_expenses({}, ctx)
        assert result["total"] == 0

    def test_with_data(self, ctx, fin_store):
        from utils.timezone_utils import today_iso_in_configured_timezone
        fin_store.create_expense(user_id=USER_ID, name="Coffee", amount=5.0,
                                    category="Alimentação",
                                    date=today_iso_in_configured_timezone())
        from assistant_connector.tools.finance_tools import list_expenses
        result = list_expenses({}, ctx)
        assert result["total"] >= 1

    def test_specific_month(self, ctx):
        from assistant_connector.tools.finance_tools import list_expenses
        result = list_expenses({"month": "2020-01"}, ctx)
        assert result["month"] == "2020-01"
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# edit_expense
# ---------------------------------------------------------------------------

class TestEditExpense:
    def test_edit_success(self, ctx, fin_store):
        from utils.timezone_utils import today_iso_in_configured_timezone
        exp = fin_store.create_expense(user_id=USER_ID, name="Coffee", amount=5.0,
                                          category="Alimentação",
                                          date=today_iso_in_configured_timezone())
        from assistant_connector.tools.finance_tools import edit_expense
        result = edit_expense({"expense_id": exp["id"], "amount": 7.5}, ctx)
        assert result["status"] == "updated"

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.finance_tools import edit_expense
        with pytest.raises(ValueError, match="expense_id"):
            edit_expense({}, ctx)


# ---------------------------------------------------------------------------
# delete_expense
# ---------------------------------------------------------------------------

class TestDeleteExpense:
    def test_delete_success(self, ctx, fin_store):
        from utils.timezone_utils import today_iso_in_configured_timezone
        exp = fin_store.create_expense(user_id=USER_ID, name="Coffee", amount=5.0,
                                          category="Alimentação",
                                          date=today_iso_in_configured_timezone())
        from assistant_connector.tools.finance_tools import delete_expense
        result = delete_expense({"expense_id": exp["id"]}, ctx)
        assert result["status"] == "deleted"

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.finance_tools import delete_expense
        with pytest.raises(ValueError, match="not found"):
            delete_expense({"expense_id": "nonexistent"}, ctx)


# ---------------------------------------------------------------------------
# register_bill
# ---------------------------------------------------------------------------

class TestRegisterBill:
    def test_register_success(self, ctx):
        from assistant_connector.tools.finance_tools import register_bill
        result = register_bill({"bill_name": "Internet", "budget": 99.90}, ctx)
        assert result["status"] == "created"
        assert result["bill"]["bill_name"] == "Internet"

    def test_missing_name_raises(self, ctx):
        from assistant_connector.tools.finance_tools import register_bill
        with pytest.raises(ValueError, match="bill_name"):
            register_bill({"budget": 100}, ctx)

    def test_missing_budget_raises(self, ctx):
        from assistant_connector.tools.finance_tools import register_bill
        with pytest.raises(ValueError, match="budget"):
            register_bill({"bill_name": "Internet"}, ctx)


# ---------------------------------------------------------------------------
# edit_bill
# ---------------------------------------------------------------------------

class TestEditBill:
    def test_edit_success(self, ctx, fin_store):
        bill = fin_store.create_bill(user_id=USER_ID, bill_name="Internet",
                                        budget=99.90, category="Moradia")
        from assistant_connector.tools.finance_tools import edit_bill
        result = edit_bill({"bill_id": bill["id"], "budget": 109.90}, ctx)
        assert result["status"] == "updated"

    def test_missing_id_raises(self, ctx):
        from assistant_connector.tools.finance_tools import edit_bill
        with pytest.raises(ValueError, match="bill_id"):
            edit_bill({}, ctx)

    def test_no_fields_raises(self, ctx, fin_store):
        bill = fin_store.create_bill(user_id=USER_ID, bill_name="Internet",
                                        budget=99.90, category="Moradia")
        from assistant_connector.tools.finance_tools import edit_bill
        with pytest.raises(ValueError, match="At least one"):
            edit_bill({"bill_id": bill["id"]}, ctx)


# ---------------------------------------------------------------------------
# delete_bill
# ---------------------------------------------------------------------------

class TestDeleteBill:
    def test_delete_success(self, ctx, fin_store):
        bill = fin_store.create_bill(user_id=USER_ID, bill_name="Internet",
                                        budget=99.90, category="Moradia")
        from assistant_connector.tools.finance_tools import delete_bill
        result = delete_bill({"bill_id": bill["id"]}, ctx)
        assert result["status"] == "deleted"

    def test_not_found_raises(self, ctx):
        from assistant_connector.tools.finance_tools import delete_bill
        with pytest.raises(ValueError, match="not found"):
            delete_bill({"bill_id": "nonexistent"}, ctx)
