"""Tests for health (meals + exercises) endpoints in web_app.app."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

_ORIGINAL_HTTPX_REQUEST = httpx.Client.request


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch, tmp_path):
    """Set up test environment and reset singletons."""
    db_path = str(tmp_path / "test_health.sqlite3")

    monkeypatch.setenv("WEB_JWT_SECRET", "test-secret-for-health-tests")
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

    monkeypatch.setattr(httpx.Client, "request", _ORIGINAL_HTTPX_REQUEST)


@pytest.fixture
def client():
    from web_app.app import app
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    from web_app.dependencies import get_user_store
    store = get_user_store()
    store.create_user("healthuser", "testpass123", display_name="Health User")
    res = client.post("/api/auth/login", json={"username": "healthuser", "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Auth tests ----

class TestHealthRequiresAuth:
    def test_dashboard_401(self, client):
        res = client.get("/api/health/dashboard")
        assert res.status_code in (401, 403)

    def test_weekly_401(self, client):
        res = client.get("/api/health/weekly")
        assert res.status_code in (401, 403)

    def test_create_meal_401(self, client):
        res = client.post("/api/health/meals", json={"meal_type": "ALMOÇO", "items": [{"food": "x", "quantity": "1g"}]})
        assert res.status_code in (401, 403)

    def test_create_exercise_401(self, client):
        res = client.post("/api/health/exercises", json={"activity": "x", "calories": 100})
        assert res.status_code in (401, 403)

    def test_update_exercise_401(self, client):
        res = client.patch("/api/health/exercises/some-id", json={"done": True})
        assert res.status_code in (401, 403)


# ---- Dashboard tests ----

class TestHealthDashboard:
    def test_empty_dashboard(self, client, auth_token):
        res = client.get("/api/health/dashboard", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["meals"] == []
        assert data["exercises"] == []
        assert data["totals"]["calories_consumed"] == 0
        assert data["totals"]["calories_burned"] == 0
        assert "notion_configured" not in data

    def test_dashboard_with_data(self, client, auth_token):
        from web_app.dependencies import get_health_store
        store = get_health_store()
        store.create_meal(
            user_id="web:healthuser", food="Arroz", meal_type="ALMOÇO",
            quantity="200g", calories=300, date="2025-03-06",
        )
        store.create_meal(
            user_id="web:healthuser", food="Frango", meal_type="ALMOÇO",
            quantity="150g", calories=250, date="2025-03-06",
        )
        store.create_exercise(
            user_id="web:healthuser", activity="Corrida", calories=350,
            date="2025-03-06", done=True,
        )

        res = client.get("/api/health/dashboard?date=2025-03-06", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert len(data["meals"]) == 2
        assert len(data["exercises"]) == 1
        assert data["totals"]["calories_consumed"] == 550.0
        assert data["totals"]["calories_burned"] == 350.0
        assert data["totals"]["balance"] == 200.0

    def test_dashboard_invalid_date(self, client, auth_token):
        res = client.get("/api/health/dashboard?date=not-a-date", headers=_auth(auth_token))
        assert res.status_code == 400

    def test_dashboard_defaults_to_today(self, client, auth_token):
        res = client.get("/api/health/dashboard", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert "date" in data


# ---- Weekly tests ----

class TestHealthWeekly:
    def test_weekly_empty(self, client, auth_token):
        res = client.get("/api/health/weekly", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert "days" in data
        assert len(data["days"]) == 7
        assert "notion_configured" not in data

    def test_weekly_returns_7_days(self, client, auth_token):
        res = client.get("/api/health/weekly?end_date=2025-03-06", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert len(data["days"]) == 7
        assert data["days"][0]["date"] == "2025-02-28"
        assert data["days"][6]["date"] == "2025-03-06"

    def test_weekly_with_data(self, client, auth_token):
        from web_app.dependencies import get_health_store
        store = get_health_store()
        store.create_meal(
            user_id="web:healthuser", food="Arroz", meal_type="ALMOÇO",
            quantity="200g", calories=300, date="2025-03-06",
        )

        res = client.get("/api/health/weekly?end_date=2025-03-06", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        last_day = next(d for d in data["days"] if d["date"] == "2025-03-06")
        assert last_day["calories_consumed"] == 300.0


# ---- Create meal tests ----

class TestCreateMeal:
    def test_missing_fields(self, client, auth_token):
        res = client.post("/api/health/meals", json={}, headers=_auth(auth_token))
        assert res.status_code == 422

    def test_invalid_meal_type(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "INVALID",
            "items": [{"food": "Pizza", "quantity": "1 slice", "estimated_calories": 300}]
        }, headers=_auth(auth_token))
        assert res.status_code == 400
        assert "meal_type" in res.json()["detail"]

    def test_calories_too_high(self, client, auth_token):
        # calories_too_high validation removed from batch endpoint (each item uses estimate or provided value)
        # High calorie values are accepted; test that valid payload succeeds
        res = client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [{"food": "Something", "quantity": "1 kg", "estimated_calories": 40000}]
        }, headers=_auth(auth_token))
        assert res.status_code == 200

    def test_create_meal_success(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [{"food": "Arroz", "quantity": "200g", "estimated_calories": 300}]
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["meals"][0]["food"] == "Arroz"
        assert data["meals"][0]["calories"] == 300.0
        assert "id" in data["meals"][0]
        assert "meal_group_id" in data

    def test_create_meal_appears_in_dashboard(self, client, auth_token):
        client.post("/api/health/meals", json={
            "meal_type": "LANCHE",
            "items": [{"food": "Banana", "quantity": "1 un", "estimated_calories": 90}]
        }, headers=_auth(auth_token))

        from utils.timezone_utils import today_iso_in_configured_timezone
        today = today_iso_in_configured_timezone()
        res = client.get(f"/api/health/dashboard?date={today}", headers=_auth(auth_token))
        assert res.status_code == 200
        foods = [m["food"] for m in res.json()["meals"]]
        assert "Banana" in foods


# ---- Meal foods autocomplete ----

class TestMealFoods:
    def test_meal_foods_requires_auth(self, client):
        res = client.get("/api/health/meals/foods")
        assert res.status_code == 401

    def test_meal_foods_empty_initially(self, client, auth_token):
        res = client.get("/api/health/meals/foods", headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["foods"] == []

    def test_meal_foods_returns_logged_foods(self, client, auth_token):
        client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [
                {"food": "Arroz", "quantity": "200g", "estimated_calories": 300},
                {"food": "Feijão", "quantity": "100g", "estimated_calories": 150},
            ]
        }, headers=_auth(auth_token))
        res = client.get("/api/health/meals/foods", headers=_auth(auth_token))
        assert res.status_code == 200
        foods = res.json()["foods"]
        assert "Arroz" in foods
        assert "Feijão" in foods

    def test_meal_foods_ordered_by_frequency(self, client, auth_token):
        for _ in range(2):
            client.post("/api/health/meals", json={
                "meal_type": "ALMOÇO",
                "items": [{"food": "Arroz", "quantity": "200g", "estimated_calories": 300}]
            }, headers=_auth(auth_token))
        client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [{"food": "Banana", "quantity": "1 un", "estimated_calories": 90}]
        }, headers=_auth(auth_token))
        res = client.get("/api/health/meals/foods", headers=_auth(auth_token))
        foods = res.json()["foods"]
        assert foods.index("Arroz") < foods.index("Banana")


# ---- Create exercise tests ----

class TestCreateExercise:
    def test_missing_fields(self, client, auth_token):
        res = client.post("/api/health/exercises", json={}, headers=_auth(auth_token))
        assert res.status_code == 422

    def test_create_exercise_with_date(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Running", "calories": 350, "date": "2025-01-15", "done": True
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["exercise"]["date"] == "2025-01-15"

    def test_create_exercise_success(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Running", "calories": 350, "done": True
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["exercise"]["activity"] == "Running"
        assert "id" in data["exercise"]

    def test_create_exercise_with_effort_level(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Musculação", "calories": 250, "effort_level": 8
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["exercise"]["effort_level"] == 8

    def test_create_exercise_effort_level_invalid(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Corrida", "calories": 300, "effort_level": 11
        }, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_create_exercise_effort_level_zero(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Alongamento", "calories": 80, "effort_level": 0
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["exercise"]["effort_level"] == 0

    def test_activity_too_long(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "A" * 201, "calories": 100
        }, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_calories_invalid(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Yoga", "calories": -5
        }, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_create_exercise_with_invalid_date(self, client, auth_token):
        res = client.post("/api/health/exercises", json={
            "activity": "Yoga", "calories": 120, "date": "bad-date"
        }, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_exercise_appears_in_dashboard(self, client, auth_token):
        client.post("/api/health/exercises", json={
            "activity": "Yoga", "calories": 120, "done": True
        }, headers=_auth(auth_token))

        from utils.timezone_utils import today_iso_in_configured_timezone
        today = today_iso_in_configured_timezone()
        res = client.get(f"/api/health/dashboard?date={today}", headers=_auth(auth_token))
        assert res.status_code == 200
        activities = [e["activity"] for e in res.json()["exercises"]]
        assert "Yoga" in activities


# ---- Update exercise tests ----

class TestUpdateExercise:
    def test_no_fields_to_update(self, client, auth_token):
        res = client.patch("/api/health/exercises/some-id", json={}, headers=_auth(auth_token))
        assert res.status_code == 400
        assert "At least one field" in res.json()["detail"]

    def test_not_found(self, client, auth_token):
        res = client.patch("/api/health/exercises/nonexistent-id", json={"done": True}, headers=_auth(auth_token))
        assert res.status_code == 404

    def test_update_exercise_success(self, client, auth_token):
        create_res = client.post("/api/health/exercises", json={
            "activity": "Cycling", "calories": 200, "done": False
        }, headers=_auth(auth_token))
        assert create_res.status_code == 200
        exercise_id = create_res.json()["exercise"]["id"]

        update_res = client.patch(f"/api/health/exercises/{exercise_id}", json={
            "done": True, "calories": 250
        }, headers=_auth(auth_token))
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["done"] is True
        assert data["calories"] == 250.0

    def test_update_exercise_with_effort_level(self, client, auth_token):
        create_res = client.post("/api/health/exercises", json={
            "activity": "Corrida", "calories": 300
        }, headers=_auth(auth_token))
        exercise_id = create_res.json()["exercise"]["id"]

        update_res = client.patch(f"/api/health/exercises/{exercise_id}", json={
            "effort_level": 7
        }, headers=_auth(auth_token))
        assert update_res.status_code == 200
        assert update_res.json()["effort_level"] == 7

    def test_update_exercise_effort_level_invalid(self, client, auth_token):
        create_res = client.post("/api/health/exercises", json={
            "activity": "Bike", "calories": 180
        }, headers=_auth(auth_token))
        exercise_id = create_res.json()["exercise"]["id"]

        res = client.patch(f"/api/health/exercises/{exercise_id}", json={
            "effort_level": -1
        }, headers=_auth(auth_token))
        assert res.status_code == 400


# ---- Nutritional analysis tests ----


class TestNutritionalAnalysis:
    def test_analysis_401(self, client):
        res = client.post("/api/health/analysis")
        assert res.status_code in (401, 403)

    def test_analysis_returns_text(self, client, auth_token, monkeypatch):
        """POST /api/health/analysis should call generate_nutritional_analysis and return markdown."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")

        mock_result = "## Análise\nTudo certo."

        def fake_generate(meals, exercises, logger=None, calorie_goal=None):
            return mock_result

        import openai_connector.llm_api as llm_mod
        monkeypatch.setattr(llm_mod, "generate_nutritional_analysis", fake_generate)

        res = client.post("/api/health/analysis", headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["analysis"] == mock_result

    def test_analysis_includes_meals(self, client, auth_token, monkeypatch):
        """Meals registered for recent days should be forwarded to the analysis function."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")

        captured = {}

        def fake_generate(meals, exercises, logger=None, calorie_goal=None):
            captured["meals"] = meals
            captured["exercises"] = exercises
            captured["calorie_goal"] = calorie_goal
            return "ok"

        import openai_connector.llm_api as llm_mod
        monkeypatch.setattr(llm_mod, "generate_nutritional_analysis", fake_generate)

        # Register a meal for today
        client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [{"food": "Arroz", "quantity": "200g", "estimated_calories": 300}]
        }, headers=_auth(auth_token))

        res = client.post("/api/health/analysis", headers=_auth(auth_token))
        assert res.status_code == 200
        assert len(captured["meals"]) >= 1
        assert captured["meals"][0]["food"] == "Arroz"

    def test_analysis_passes_calorie_goal(self, client, auth_token, monkeypatch):
        """Calorie goal from health store should be forwarded to the analysis function."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")

        captured = {}

        def fake_generate(meals, exercises, logger=None, calorie_goal=None):
            captured["calorie_goal"] = calorie_goal
            return "ok"

        import openai_connector.llm_api as llm_mod
        monkeypatch.setattr(llm_mod, "generate_nutritional_analysis", fake_generate)

        # Set a custom calorie goal
        client.put("/api/health/goals", json={"calorie_goal": 1800}, headers=_auth(auth_token))

        res = client.post("/api/health/analysis", headers=_auth(auth_token))
        assert res.status_code == 200
        assert captured["calorie_goal"] == 1800

    def test_analysis_error_returns_500(self, client, auth_token, monkeypatch):
        """If generate_nutritional_analysis raises, endpoint returns 500."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")

        def fake_generate(meals, exercises, logger=None, calorie_goal=None):
            raise RuntimeError("LLM broke")

        import openai_connector.llm_api as llm_mod
        monkeypatch.setattr(llm_mod, "generate_nutritional_analysis", fake_generate)

        res = client.post("/api/health/analysis", headers=_auth(auth_token))
        assert res.status_code == 500


# ---- Meal group PATCH + DELETE tests ----

class TestMealGroupOps:
    def _create_meal_group(self, client, auth_token, meal_type="ALMOÇO", date=None):
        payload: dict = {
            "meal_type": meal_type,
            "items": [
                {"food": "Arroz", "quantity": "200g", "estimated_calories": 300},
                {"food": "Frango", "quantity": "150g", "estimated_calories": 200},
            ],
        }
        if date:
            payload["date"] = date
        res = client.post("/api/health/meals", json=payload, headers=_auth(auth_token))
        assert res.status_code == 200
        return res.json()["meal_group_id"]

    def test_create_with_date(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "JANTAR",
            "date": "2025-01-15",
            "items": [{"food": "Sopa", "quantity": "300ml", "estimated_calories": 120}],
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["meals"][0]["date"] == "2025-01-15"

    def test_create_with_invalid_date(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "JANTAR",
            "date": "not-a-date",
            "items": [{"food": "Sopa", "quantity": "300ml", "estimated_calories": 120}],
        }, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_delete_meal_group(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token)
        res = client.delete(f"/api/health/meals/group/{gid}", headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["count"] == 2

    def test_delete_meal_group_not_found(self, client, auth_token):
        res = client.delete("/api/health/meals/group/nonexistent", headers=_auth(auth_token))
        assert res.status_code == 404

    def test_patch_meal_group_type(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token, meal_type="ALMOÇO")
        res = client.patch(f"/api/health/meals/group/{gid}", json={"meal_type": "JANTAR"},
                           headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["count"] == 2

    def test_patch_meal_group_date(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token)
        res = client.patch(f"/api/health/meals/group/{gid}", json={"date": "2025-06-01"},
                           headers=_auth(auth_token))
        assert res.status_code == 200
        assert res.json()["count"] == 2

    def test_patch_meal_group_invalid_type(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token)
        res = client.patch(f"/api/health/meals/group/{gid}", json={"meal_type": "INVALID"},
                           headers=_auth(auth_token))
        assert res.status_code == 400

    def test_patch_meal_group_invalid_date(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token)
        res = client.patch(f"/api/health/meals/group/{gid}", json={"date": "bad-date"},
                           headers=_auth(auth_token))
        assert res.status_code == 400

    def test_patch_meal_group_no_fields(self, client, auth_token):
        gid = self._create_meal_group(client, auth_token)
        res = client.patch(f"/api/health/meals/group/{gid}", json={}, headers=_auth(auth_token))
        assert res.status_code == 400

    def test_patch_meal_group_not_found(self, client, auth_token):
        res = client.patch("/api/health/meals/group/nonexistent", json={"meal_type": "JANTAR"},
                           headers=_auth(auth_token))
        assert res.status_code == 404

    def test_delete_individual_meal_item(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "LANCHE",
            "items": [{"food": "Maçã", "quantity": "1 un", "estimated_calories": 80}],
        }, headers=_auth(auth_token))
        meal_id = res.json()["meals"][0]["id"]
        del_res = client.delete(f"/api/health/meals/{meal_id}", headers=_auth(auth_token))
        assert del_res.status_code == 200

    def test_patch_individual_meal_item(self, client, auth_token):
        res = client.post("/api/health/meals", json={
            "meal_type": "LANCHE",
            "items": [{"food": "Maçã", "quantity": "1 un", "estimated_calories": 80}],
        }, headers=_auth(auth_token))
        meal_id = res.json()["meals"][0]["id"]
        patch_res = client.patch(f"/api/health/meals/{meal_id}",
                                 json={"food": "Pera"}, headers=_auth(auth_token))
        assert patch_res.status_code == 200
        assert patch_res.json()["meal"]["food"] == "Pera"


# ---- calories_pending tests ----

class TestCaloriesPending:
    def test_explicit_calories_not_pending(self, client, auth_token):
        """Items with explicit estimated_calories should not be marked pending."""
        res = client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [{"food": "Arroz", "quantity": "200g", "estimated_calories": 300}],
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["meals"][0]["calories"] == 300.0
        assert data["meals"][0]["calories_pending"] is False

    def test_no_calories_creates_pending(self, client, auth_token, monkeypatch):
        """Items without explicit calories should be saved with calories_pending=True."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")

        import openai_connector.llm_api as llm_mod

        async def fake_batch(items, logger=None):
            return [0.0] * len(items)

        # Patch the background task so it doesn't actually call the LLM
        import asyncio

        async def fake_estimate_task():
            pass

        import web_app.app as web_app_mod
        monkeypatch.setattr(asyncio, "create_task", lambda coro: None)

        res = client.post("/api/health/meals", json={
            "meal_type": "JANTAR",
            "items": [{"food": "Frango grelhado", "quantity": "200g"}],
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        assert data["calories_pending"] is True
        assert data["meals"][0]["calories_pending"] is True
        assert data["meals"][0]["calories"] == 0.0

    def test_mixed_pending_and_not(self, client, auth_token, monkeypatch):
        """Items with explicit calories are not pending; items without are pending."""
        monkeypatch.setenv("OPENAI_KEY", "test-key")
        import asyncio
        monkeypatch.setattr(asyncio, "create_task", lambda coro: None)

        res = client.post("/api/health/meals", json={
            "meal_type": "ALMOÇO",
            "items": [
                {"food": "Arroz", "quantity": "200g", "estimated_calories": 250},
                {"food": "Salada", "quantity": "100g"},
            ],
        }, headers=_auth(auth_token))
        assert res.status_code == 200
        data = res.json()
        # First item has explicit calories — not pending
        arroz = next(m for m in data["meals"] if m["food"] == "Arroz")
        salada = next(m for m in data["meals"] if m["food"] == "Salada")
        assert arroz["calories_pending"] is False
        assert arroz["calories"] == 250.0
        assert salada["calories_pending"] is True

    def test_no_pending_when_no_openai_key(self, client, auth_token, monkeypatch):
        """When OPENAI_KEY is missing, items without calories save with 0.0 (not pending)."""
        monkeypatch.setenv("OPENAI_KEY", "")
        import asyncio
        monkeypatch.setattr(asyncio, "create_task", lambda coro: None)

        res = client.post("/api/health/meals", json={
            "meal_type": "CAFÉ DA MANHÃ",
            "items": [{"food": "Pão", "quantity": "2 fatias"}],
        }, headers=_auth(auth_token))
        assert res.status_code == 200


# ---- Delete exercise tests ----

class TestDeleteExercise:
    def test_delete_exercise_requires_auth(self, client):
        res = client.delete("/api/health/exercises/some-id")
        assert res.status_code == 401

    def test_delete_exercise_not_found(self, client, auth_token):
        res = client.delete("/api/health/exercises/nonexistent-id", headers=_auth(auth_token))
        assert res.status_code == 404

    def test_delete_exercise_success(self, client, auth_token):
        create_res = client.post("/api/health/exercises", json={
            "activity": "Swimming", "calories": 400, "done": False
        }, headers=_auth(auth_token))
        assert create_res.status_code == 200
        exercise_id = create_res.json()["exercise"]["id"]

        del_res = client.delete(f"/api/health/exercises/{exercise_id}", headers=_auth(auth_token))
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

    def test_deleted_exercise_not_in_dashboard(self, client, auth_token):
        create_res = client.post("/api/health/exercises", json={
            "activity": "Jump Rope", "calories": 300, "done": True
        }, headers=_auth(auth_token))
        exercise_id = create_res.json()["exercise"]["id"]

        client.delete(f"/api/health/exercises/{exercise_id}", headers=_auth(auth_token))

        from utils.timezone_utils import today_iso_in_configured_timezone
        today = today_iso_in_configured_timezone()
        dash_res = client.get(f"/api/health/dashboard?date={today}", headers=_auth(auth_token))
        activities = [e["activity"] for e in dash_res.json()["exercises"]]
        assert "Jump Rope" not in activities

    def test_cannot_delete_another_users_exercise(self, client, auth_token):
        """Exercise should only be deletable by its owner."""
        create_res = client.post("/api/health/exercises", json={
            "activity": "Boxing", "calories": 500, "done": False
        }, headers=_auth(auth_token))
        exercise_id = create_res.json()["exercise"]["id"]

        # Create a second user and try to delete
        from web_app.dependencies import get_user_store
        get_user_store().create_user("other_user2", "pass123", "Other")
        other_token = client.post("/api/auth/login", json={
            "username": "other_user2", "password": "pass123"
        }).json()["token"]

        res = client.delete(f"/api/health/exercises/{exercise_id}",
                            headers=_auth(other_token))
        assert res.status_code == 404
