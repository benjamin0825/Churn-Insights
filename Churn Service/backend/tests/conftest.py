"""Test setup: an isolated data directory, an in-process app, and inline background jobs."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("service-data")
    os.environ["CHURN_SERVICE_DATA_DIR"] = str(path)
    os.environ["CHURN_SERVICE_FRONTEND_DIST"] = str(path / "no-frontend")
    return path


@pytest.fixture(scope="session")
def client(data_dir):
    from app import jobs
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import create_app

    # Run background jobs synchronously so tests are deterministic.
    original = jobs.submit

    def inline_submit(db, org_id, user_id, kind, params=None, run_inline=False):
        return original(db, org_id, user_id, kind, params, run_inline=True)

    jobs.submit = inline_submit
    with TestClient(create_app()) as test_client:
        yield test_client
    jobs.submit = original


def register(client, email="owner@example.com", org="Acme Telecom"):
    response = client.post("/api/auth/register", json={"organization": org, "name": "Ada Owner", "email": email,
                                                       "password": "correct-horse-battery"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def auth(client):
    return register(client)


@pytest.fixture(scope="session")
def trained(client, auth):
    """Demo data + quick training, done once for the whole session."""
    response = client.post("/api/data/demo", data={"customers": 2000, "profile": "quick"}, headers=auth)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "succeeded", job.get("error")
    return job
