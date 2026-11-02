"""End-to-end API tests: auth, demo data, training, customers, dashboard, campaigns, models, monitoring."""

import io

from conftest import register


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["kernel_backend"] in {"ext", "native", "numpy"}


def test_auth_flow(client):
    headers = register(client, email="analyst@example.com", org="Beta Fiber")
    me = client.get("/api/me", headers=headers).json()
    assert me["email"] == "analyst@example.com" and me["organization"]["name"] == "Beta Fiber"
    assert client.post("/api/auth/login", json={"email": "ANALYST@example.com",
                                                "password": "correct-horse-battery"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "analyst@example.com", "password": "wrong-password"}
                       ).status_code == 401
    duplicate = client.post("/api/auth/register", json={"organization": "Gamma", "name": "Y",
                                                        "email": "analyst@example.com", "password": "another-password"})
    assert duplicate.status_code == 409


def test_endpoints_require_auth(client):
    for path in ("/api/me", "/api/dashboard", "/api/customers", "/api/models", "/api/data/status"):
        assert client.get(path).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_no_scores_before_data(client):
    headers = register(client, email="empty@example.com", org="Empty Co")
    status = client.get("/api/data/status", headers=headers).json()
    assert status["has_data"] is False and status["has_model"] is False
    assert client.get("/api/dashboard", headers=headers).status_code == 409
    assert client.post("/api/models/train", data={"profile": "quick"}, headers=headers).status_code == 409


def test_demo_training_populates_everything(client, auth, trained):
    result = trained["result"]
    assert result["version"] == 1 and result["promoted"]
    assert result["test_roc_auc"] > 0.65 and result["scored"] > 500
    status = client.get("/api/data/status", headers=auth).json()
    assert status["has_data"] and status["has_model"] and status["has_scores"]
    assert status["dataset"]["source"] == "demo"


def test_dashboard(client, auth, trained):
    body = client.get("/api/dashboard", headers=auth).json()
    kpis = body["kpis"]
    assert kpis["customers"] > 500 and 0 < kpis["avg_churn_probability"] < 1
    assert {t["tier"] for t in body["tiers"]} == {"high", "medium", "low"}
    assert body["churn_trend"] and body["drivers"] and body["model"]["roc_auc"] > 0.65
    assert {r["segment"] for r in body["by_region"]} == {"north", "south", "east", "west"}


def test_overview_metrics(client, auth, trained):
    body = client.get("/api/overview?period=12w", headers=auth).json()
    cards = {c["key"]: c for c in body["cards"]}
    assert {"mrr", "active_customers", "user_churn_rate", "arpu", "ltv", "new_customers"} <= set(cards)
    assert cards["mrr"]["value"] > 0 and len(cards["mrr"]["series"]) == 12
    assert 0 <= cards["user_churn_rate"]["value"] < 1
    assert abs(cards["arpu"]["value"] - cards["mrr"]["value"] / cards["active_customers"]["value"]) < 0.01
    b = body["breakdown"]
    assert abs(b["net_mrr_change"] - (b["new_mrr"] + b["expansion_mrr"] + b["contraction_mrr"] + b["churned_mrr"])) < 0.01
    assert body["activity"] and body["forecast"]["customers"] > 0
    assert len({e["kind"] for e in body["activity"]}) > 1  # the feed mixes event kinds
    empty = register(client, email="nodata@example.com", org="No Data Co")
    assert client.get("/api/overview", headers=empty).status_code == 409


def test_customer_list_filters_and_detail(client, auth, trained):
    page = client.get("/api/customers?tier=high&sort=probability&page_size=10", headers=auth).json()
    assert page["total"] > 0 and len(page["items"]) <= 10
    probabilities = [c["churn_probability"] for c in page["items"]]
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(c["risk_tier"] == "high" for c in page["items"])
    west = client.get("/api/customers?region=west&page_size=5", headers=auth).json()
    assert all(c["region"] == "west" for c in west["items"])

    customer_id = page["items"][0]["customer_id"]
    detail = client.get(f"/api/customers/{customer_id}", headers=auth).json()
    assert detail["customer_id"] == customer_id and detail["score"]["risk_tier"] == "high"
    assert len(detail["reasons"]) == 8 and detail["history"]["usage"]
    assert client.get("/api/customers/999999999", headers=auth).status_code == 404


def test_campaign_preview_create_export(client, auth, trained):
    params = {"offer_cost": 15, "retention_success_rate": 0.35, "months_of_value": 12, "budget": 3000,
              "risk_tiers": ["high", "medium"]}
    preview = client.post("/api/campaigns/preview", json=params, headers=auth).json()
    summary = preview["summary"]
    assert 0 < summary["targeted_customers"] <= 200  # budget 3000 / cost 15
    assert summary["campaign_cost"] <= 3000 and summary["expected_profit"] > 0
    assert preview["curve"] and preview["top_targets"]

    created = client.post("/api/campaigns", json={**params, "name": "Q4 save offer"}, headers=auth)
    assert created.status_code == 201
    campaign_id = created.json()["id"]
    assert client.get("/api/campaigns", headers=auth).json()[0]["id"] == campaign_id
    export = client.get(f"/api/campaigns/{campaign_id}/export", headers=auth)
    assert export.status_code == 200 and export.text.startswith("customer_id,")
    assert len(export.text.strip().splitlines()) == summary["targeted_customers"] + 1

    other = register(client, email="intruder@example.com", org="Other Org")
    assert client.get(f"/api/campaigns/{campaign_id}", headers=other).status_code == 404  # tenant isolation
    assert client.delete(f"/api/campaigns/{campaign_id}", headers=auth).status_code == 204


def test_models_and_monitoring(client, auth, trained):
    models = client.get("/api/models", headers=auth).json()
    assert models["production"] == 1 and models["versions"][0]["stage"] == "production"
    detail = client.get("/api/models/1", headers=auth).json()
    assert detail["is_production"] and detail["leaderboard"]
    report = client.get("/api/models/1/report", headers=auth)
    assert report.status_code == 200 and "<html" in report.text
    drift = client.get("/api/monitoring/drift", headers=auth).json()
    assert drift["status"] in {"stable", "warning", "alert"} and drift["features"]
    assert client.get("/api/monitoring/drift/report", headers=auth).status_code == 200


def test_upload_round_trip_and_validation(client, trained):
    headers = register(client, email="uploader@example.com", org="Upload Co")
    tables = {name: client.get(f"/api/data/template/{name}", headers=headers).text
              for name in ("customers", "usage", "billing", "tickets")}
    files = {name: (f"{name}.csv", io.BytesIO(text.encode()), "text/csv") for name, text in tables.items()}
    response = client.post("/api/data/upload", files=files, data={"train": "false"}, headers=headers)
    assert response.status_code == 202, response.text
    assert response.json()["summary"]["customers"] == 40
    assert client.get("/api/data/status", headers=headers).json()["has_data"] is True

    broken = dict(tables, usage=tables["usage"].replace("sessions", "visits", 1))
    files = {name: (f"{name}.csv", io.BytesIO(text.encode()), "text/csv") for name, text in broken.items()}
    bad = client.post("/api/data/upload", files=files, data={"train": "false"}, headers=headers)
    assert bad.status_code == 422 and "missing column 'sessions'" in str(bad.json())


def test_economics_update(client, auth):
    body = {"offer_cost": 20, "retention_success_rate": 0.4, "months_of_value": 10}
    updated = client.put("/api/organization/economics", json=body, headers=auth).json()
    assert updated["offer_cost"] == 20 and client.get("/api/me", headers=auth).json()["organization"]["offer_cost"] == 20


def test_demo_customers_have_names(client, auth, trained):
    from app.names import demo_name

    page = client.get("/api/customers?page_size=5", headers=auth).json()
    first = page["items"][0]
    assert first["name"] == demo_name(first["customer_id"]) and " " in first["name"]
    detail = client.get(f"/api/customers/{first['customer_id']}", headers=auth).json()
    assert detail["name"] == first["name"]
    by_name = client.get(f"/api/customers?search={first['name'].split()[1]}", headers=auth).json()
    assert any(i["customer_id"] == first["customer_id"] for i in by_name["items"]) or by_name["total"] > 0
    activity = client.get("/api/overview", headers=auth).json()["activity"]
    assert all(e["name"] for e in activity)
