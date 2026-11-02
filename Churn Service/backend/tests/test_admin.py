"""Site administration: access control, workspaces, users, jobs, plans and the schema upgrade."""

import pytest
from conftest import register
from sqlalchemy import create_engine, inspect, text


def _user(email):
    from app.db import session_factory
    from app.models import User

    with session_factory()() as db:
        return db.query(User).filter(User.email == email).one()


def _set(email, **fields):
    from app.db import session_factory
    from app.models import User

    with session_factory()() as db:
        user = db.query(User).filter(User.email == email).one()
        for key, value in fields.items():
            setattr(user, key, value)
        db.commit()


@pytest.fixture(scope="module")
def admin(client):
    headers = register(client, email="root@example.com", org="Operators")
    _set("root@example.com", is_admin=True)
    return headers


def login(client, email, password="correct-horse-battery"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_admin_routes_need_an_admin(client, admin):
    customer = register(client, email="plain@example.com", org="Plain Co")
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/admin/stats", headers=customer).status_code == 403
    assert client.get("/api/admin/users", headers=customer).status_code == 403
    assert client.get("/api/me", headers=customer).json()["is_admin"] is False
    assert client.get("/api/me", headers=admin).json()["is_admin"] is True


def test_signup_never_grants_admin(client):
    response = client.post("/api/auth/register", json={"organization": "Sneaky", "name": "S", "email": "sneaky@example.com",
                                                        "password": "correct-horse-battery", "is_admin": True})
    assert response.status_code == 201 and response.json()["user"]["is_admin"] is False


def test_stats(client, admin):
    body = client.get("/api/admin/stats", headers=admin).json()
    assert body["organizations"] >= 2 and body["users"] >= 2 and body["admins"] >= 1
    assert len(body["signups_by_week"]) == 12 and sum(w["organizations"] for w in body["signups_by_week"]) >= 2
    assert {"queued", "running", "failed_7d", "total"} <= set(body["jobs"])
    assert any(p["plan"] == "starter" for p in body["by_plan"])


def test_organizations_search_and_plan(client, admin):
    register(client, email="owner@zeta.example.com", org="Zeta Streaming")
    found = client.get("/api/admin/organizations?q=zeta", headers=admin).json()
    assert found["total"] == 1
    org = found["items"][0]
    assert org["name"] == "Zeta Streaming" and org["owner_email"] == "owner@zeta.example.com" and org["plan"] == "starter"
    by_email = client.get("/api/admin/organizations?q=owner@zeta", headers=admin).json()
    assert by_email["total"] == 1
    updated = client.patch(f"/api/admin/organizations/{org['id']}", json={"plan": "growth"}, headers=admin).json()
    assert updated["plan"] == "growth" and updated["users_list"][0]["email"] == "owner@zeta.example.com"
    assert client.patch(f"/api/admin/organizations/{org['id']}", json={"plan": "nope"}, headers=admin).status_code == 422
    assert client.get("/api/admin/organizations?plan=growth", headers=admin).json()["total"] >= 1


def test_suspend_locks_out_the_workspace(client, admin):
    headers = register(client, email="owner@suspend.example.com", org="Suspend Me")
    org_id = client.get("/api/me", headers=headers).json()["organization"]["id"]
    client.patch(f"/api/admin/organizations/{org_id}", json={"status": "suspended"}, headers=admin)
    assert client.get("/api/me", headers=headers).status_code == 403
    assert login(client, "owner@suspend.example.com").status_code == 403
    client.patch(f"/api/admin/organizations/{org_id}", json={"status": "active"}, headers=admin)
    assert client.get("/api/me", headers=headers).status_code == 200
    own = client.get("/api/me", headers=admin).json()["organization"]["id"]
    assert client.patch(f"/api/admin/organizations/{own}", json={"status": "suspended"}, headers=admin).status_code == 409


def test_users_disable_reset_and_guards(client, admin):
    headers = register(client, email="owner@users.example.com", org="Users Co")
    uid = client.get("/api/me", headers=headers).json()["id"]
    assert client.get("/api/admin/users?q=users.example", headers=admin).json()["total"] == 1

    assert client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=admin).json()["is_active"] is False
    assert client.get("/api/me", headers=headers).status_code == 403
    assert login(client, "owner@users.example.com").status_code == 403
    client.patch(f"/api/admin/users/{uid}", json={"is_active": True}, headers=admin)

    temporary = client.post(f"/api/admin/users/{uid}/reset-password", headers=admin).json()["temporary_password"]
    assert login(client, "owner@users.example.com").status_code == 401
    assert login(client, "owner@users.example.com", temporary).status_code == 200

    # the only owner can't be demoted; an admin can't lock themselves out
    assert client.patch(f"/api/admin/users/{uid}", json={"role": "analyst"}, headers=admin).status_code == 409
    me = client.get("/api/me", headers=admin).json()["id"]
    assert client.patch(f"/api/admin/users/{me}", json={"is_admin": False}, headers=admin).status_code == 409
    assert client.patch(f"/api/admin/users/{me}", json={"is_active": False}, headers=admin).status_code == 409


def test_stuck_job_can_be_marked_failed(client, admin):
    from app import jobs
    from app.db import session_factory
    from app.models import Job

    headers = register(client, email="owner@stuck.example.com", org="Stuck Co")
    org_id = client.get("/api/me", headers=headers).json()["organization"]["id"]
    with session_factory()() as db:
        job = Job(organization_id=org_id, kind="train", status="running", message="interrupted by restart")
        db.add(job)
        db.commit()
        job_id = job.id
    assert client.post("/api/models/train", data={"profile": "quick"}, headers=headers).status_code == 409
    listed = client.get(f"/api/admin/jobs?status=running&organization_id={org_id}", headers=admin).json()
    assert [j["id"] for j in listed["items"]] == [job_id] and listed["items"][0]["organization_name"] == "Stuck Co"
    assert client.post(f"/api/admin/jobs/{job_id}/fail", headers=admin).json()["status"] == "failed"
    assert client.post(f"/api/admin/jobs/{job_id}/fail", headers=admin).status_code == 409
    with session_factory()() as db:
        assert jobs.active_job(db, org_id) is None


def test_plans_crud_and_public_list(client, admin):
    public = client.get("/api/plans").json()
    assert [p["key"] for p in public] == ["starter", "growth", "scale"]
    assert sum(p["popular"] for p in public) == 1

    plan = {"key": "enterprise", "name": "Enterprise", "monthly_price": 999, "blurb": "Big", "limits": ["Unlimited"],
            "features": ["Everything", "  ", "SSO"], "popular": True, "active": True, "sort_order": 4}
    created = client.post("/api/admin/plans", json=plan, headers=admin)
    assert created.status_code == 201 and created.json()["features"] == ["Everything", "SSO"]
    assert client.post("/api/admin/plans", json=plan, headers=admin).status_code == 409
    public = client.get("/api/plans").json()
    assert [p["key"] for p in public if p["popular"]] == ["enterprise"]  # only one popular plan

    hidden = client.put("/api/admin/plans/enterprise", json={**plan, "active": False}, headers=admin).json()
    assert hidden["active"] is False and "enterprise" not in [p["key"] for p in client.get("/api/plans").json()]
    assert client.delete("/api/admin/plans/starter", headers=admin).status_code == 409  # workspaces use it
    assert client.delete("/api/admin/plans/enterprise", headers=admin).status_code == 204
    assert client.put("/api/admin/plans/growth", json={**plan, "key": "growth", "popular": True}, headers=admin).status_code == 200
    assert client.post("/api/admin/plans", json={**plan, "key": "Bad Key"}, headers=admin).status_code == 422


def test_delete_organization(client, admin):
    from app.workspace import Workspace

    headers = register(client, email="owner@delete.example.com", org="Delete Me")
    org_id = client.get("/api/me", headers=headers).json()["organization"]["id"]
    root = Workspace(org_id).root
    root.mkdir(parents=True, exist_ok=True)
    (root / "marker.txt").write_text("x")
    assert client.delete(f"/api/admin/organizations/{org_id}", headers=admin).status_code == 204
    assert not root.exists()
    assert client.get(f"/api/admin/organizations/{org_id}", headers=admin).status_code == 404
    assert client.get("/api/me", headers=headers).status_code == 401  # the user went with it
    own = client.get("/api/me", headers=admin).json()["organization"]["id"]
    assert client.delete(f"/api/admin/organizations/{own}", headers=admin).status_code == 409


def test_cli_make_admin(client, capsys):
    from app import cli

    register(client, email="promote@example.com", org="Promote Co")
    cli.make_admin("Promote@Example.com")
    assert _user("promote@example.com").is_admin is True
    cli.revoke_admin("promote@example.com")
    assert _user("promote@example.com").is_admin is False
    assert "administrator" in capsys.readouterr().out


def test_old_database_gets_new_columns(tmp_path):
    from app.db import _add_missing_columns

    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR(200))"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(320))"))
        conn.execute(text("INSERT INTO organizations (id, name) VALUES (1, 'Old Co')"))
    _add_missing_columns(engine)
    _add_missing_columns(engine)  # idempotent
    cols = {c["name"] for c in inspect(engine).get_columns("organizations")}
    assert {"plan", "status"} <= cols
    with engine.connect() as conn:
        assert conn.execute(text("SELECT plan, status FROM organizations")).one() == ("starter", "active")
    assert {"is_admin", "is_active"} <= {c["name"] for c in inspect(engine).get_columns("users")}
