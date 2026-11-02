"""Uploads too small to train on: data is kept, training is skipped or fails with a plain explanation."""

from conftest import register


def test_tiny_upload_skips_training_and_explains(client):
    headers = register(client, email="tiny@example.com", org="Tiny Co")
    files = {t: (f"{t}.csv", client.get(f"/api/data/template/{t}", headers=headers).content, "text/csv")
             for t in ("customers", "usage", "billing", "tickets")}
    response = client.post("/api/data/upload", files=files, data={"train": "true", "profile": "quick"}, headers=headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job"] is None
    assert any(w.startswith("Training was skipped.") and "at least 30" in w for w in body["warnings"])
    assert client.get("/api/data/status", headers=headers).json()["has_data"] is True  # the data is still saved

    # Training it anyway fails with a readable message, which the status reports as the last job
    job = client.post("/api/models/train", data={"profile": "quick"}, headers=headers).json()
    assert job["status"] == "failed"
    assert "needed to train a model" in job["error"] and "Traceback" not in job["error"]
    last = client.get("/api/data/status", headers=headers).json()["last_job"]
    assert last["id"] == job["id"] and last["status"] == "failed"
