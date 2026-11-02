import pytest
from fastapi.testclient import TestClient

from churn_ml.serving import create_app
from churn_ml.training.dataset import build_scoring_frame

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def client(trained, settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(scope="module")
def records(settings, raw):
    frame, _ = build_scoring_frame(settings, raw)
    frame = frame.drop(columns=["churned"])
    return frame.head(300).astype(object).where(frame.head(300).notna(), None).to_dict(orient="records")


def test_health_and_model_info(client, trained):
    assert client.get("/health").json()["model_version"] == trained.version
    info = client.get("/model").json()
    assert info["version"] == trained.version
    assert "roc_auc" in info["test_metrics"] and info["features"]["text"] == "ticket_text"


def test_predict_with_explanations(client, records):
    response = client.post("/predict?explain=true", json=records[:5])
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["predictions"]) == 5
    first = body["predictions"][0]
    assert 0 <= first["churn_probability"] <= 1 and first["reasons"]


def test_predict_rejects_unknown_fields_and_bad_types(client, records):
    bad = dict(records[0], favourite_colour="blue")
    assert client.post("/predict", json=[bad]).status_code == 422
    bad = dict(records[0], age="old")
    assert client.post("/predict", json=[bad]).status_code == 422
    assert client.post("/predict", json=[]).status_code == 422


def test_predict_rejects_negative_counts(client, records):
    bad = dict(records[0], tickets_4w=-3)
    response = client.post("/predict", json=[bad])
    assert response.status_code == 422 and "tickets_4w" in response.text


def test_score_customers_from_the_store(client, records):
    ids = [records[0]["customer_id"], records[1]["customer_id"], 99_999_999]
    response = client.post("/customers/score", json={"customer_ids": ids, "explain": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["not_found"] == [99_999_999]
    assert {p["customer_id"] for p in body["predictions"]} == set(ids[:2])


def test_drift_endpoint(client, records):
    response = client.post("/drift", json=records)
    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"stable", "warning", "alert"}
    assert client.post("/drift", json=records[:10]).status_code == 422


def test_metrics_and_reload(client, trained):
    assert client.post("/admin/reload").json()["model_version"] == trained.version
    text = client.get("/metrics").text
    assert "churn_http_requests_total" in text and f"churn_model_version {trained.version}" in text
