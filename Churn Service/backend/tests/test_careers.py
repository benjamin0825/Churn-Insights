"""Careers: postings managed by admins, public listing, applications with CVs."""

import pytest
from conftest import register

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"

POSTING = {
    "title": "AI Engineer", "department": "Engineering", "location": "Remote (Europe)", "workplace": "remote",
    "employment_type": "full_time", "salary_range": "$120k–$160k", "summary": "Build the churn models.",
    "description": "First paragraph.\n\nSecond paragraph.", "responsibilities": ["Train models", " "],
    "requirements": ["Python"], "nice_to_have": [], "benefits": ["Remote"], "status": "draft",
}


@pytest.fixture(scope="module")
def admin(client):
    from app.db import session_factory
    from app.models import User

    headers = register(client, email="hiring@example.com", org="Hiring Ops")
    with session_factory()() as db:
        db.query(User).filter(User.email == "hiring@example.com").update({User.is_admin: True})
        db.commit()
    return headers


@pytest.fixture(autouse=True)
def no_rate_limit():
    from app.routers import careers

    careers._recent.clear()


def apply(client, slug, **fields):
    data = {"name": "Grace Hopper", "email": "grace@example.com", **{k: v for k, v in fields.items() if k != "files"}}
    return client.post(f"/api/careers/{slug}/apply", data=data, files=fields.get("files"))


def test_only_admins_manage_postings(client, admin):
    customer = register(client, email="nothiring@example.com", org="Not Hiring")
    assert client.get("/api/admin/careers/postings").status_code == 401
    assert client.post("/api/admin/careers/postings", json=POSTING, headers=customer).status_code == 403


def test_draft_publish_close(client, admin):
    created = client.post("/api/admin/careers/postings", json=POSTING, headers=admin).json()
    assert created["slug"] == "ai-engineer" and created["responsibilities"] == ["Train models"]
    assert created["published_at"] is None
    slug = created["slug"]
    # drafts are invisible to the public
    assert all(p["slug"] != slug for p in client.get("/api/careers").json())
    assert client.get(f"/api/careers/{slug}").status_code == 404
    assert apply(client, slug).status_code == 404

    opened = client.put(f"/api/admin/careers/postings/{created['id']}", json={**POSTING, "status": "open"}, headers=admin).json()
    assert opened["published_at"] is not None
    assert [p["title"] for p in client.get("/api/careers").json()] == ["AI Engineer"]
    assert client.get(f"/api/careers/{slug}").json()["salary_range"] == "$120k–$160k"

    closed = {**POSTING, "status": "closed"}
    client.put(f"/api/admin/careers/postings/{created['id']}", json=closed, headers=admin)
    assert client.get("/api/careers").json() == []
    assert client.get(f"/api/careers/{slug}").status_code == 200  # link keeps working
    assert apply(client, slug).status_code == 409
    client.put(f"/api/admin/careers/postings/{created['id']}", json={**POSTING, "status": "open"}, headers=admin)


def test_slugs_are_unique(client, admin):
    second = client.post("/api/admin/careers/postings", json={**POSTING, "title": "AI Engineer"}, headers=admin).json()
    assert second["slug"] == "ai-engineer-2"
    client.delete(f"/api/admin/careers/postings/{second['id']}", headers=admin)


def test_apply_with_cv_and_review(client, admin, data_dir):
    files = {"resume": ("Grace CV.pdf", PDF, "application/pdf")}
    response = apply(client, "ai-engineer", linkedin_url="linkedin.com/in/grace", cover_letter="Hello!", files=files)
    assert response.status_code == 201, response.text

    apps = client.get("/api/admin/careers/applications", headers=admin).json()
    mine = next(a for a in apps if a["id"] == response.json()["id"])
    assert mine["posting_title"] == "AI Engineer" and mine["status"] == "new" and mine["has_resume"]
    assert mine["linkedin_url"] == "https://linkedin.com/in/grace" and mine["resume_filename"] == "Grace CV.pdf"
    postings = client.get("/api/admin/careers/postings", headers=admin).json()
    assert next(p for p in postings if p["slug"] == "ai-engineer")["new_applications"] >= 1

    cv = client.get(f"/api/admin/careers/applications/{mine['id']}/resume", headers=admin)
    assert cv.status_code == 200 and cv.content == PDF and "Grace" in cv.headers["content-disposition"]
    assert client.get(f"/api/admin/careers/applications/{mine['id']}/resume").status_code == 401

    updated = client.patch(f"/api/admin/careers/applications/{mine['id']}", json={"status": "interview", "notes": "Strong"},
                           headers=admin).json()
    assert updated["status"] == "interview" and updated["notes"] == "Strong"
    stored = list((data_dir / "applications").rglob("*.pdf"))
    assert stored and all("Grace" not in p.name for p in stored)  # stored under a random name

    assert client.delete(f"/api/admin/careers/applications/{mine['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/admin/careers/applications/{mine['id']}/resume", headers=admin).status_code == 404


def test_apply_validation(client, admin):
    assert apply(client, "ai-engineer", email="not-an-email").status_code == 422
    assert apply(client, "ai-engineer", files={"resume": ("cv.exe", b"MZ", "application/octet-stream")}).status_code == 422
    assert apply(client, "ai-engineer", files={"resume": ("cv.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    big = b"%PDF" + b"0" * (5 * 1024 * 1024)
    assert apply(client, "ai-engineer", files={"resume": ("cv.pdf", big, "application/pdf")}).status_code == 413
    assert apply(client, "ai-engineer", portfolio_url="javascript alert(1)").status_code == 422
    assert apply(client, "no-such-job").status_code == 404


def test_honeypot_and_rate_limit(client, admin):
    before = len(client.get("/api/admin/careers/applications", headers=admin).json())
    assert apply(client, "ai-engineer", website="http://spam.example").status_code == 201
    assert len(client.get("/api/admin/careers/applications", headers=admin).json()) == before  # silently dropped
    codes = [apply(client, "ai-engineer", email=f"a{i}@example.com").status_code for i in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_delete_posting_removes_applications(client, admin, data_dir):
    posting = client.post("/api/admin/careers/postings", json={**POSTING, "title": "Full Stack Engineer", "status": "open"},
                          headers=admin).json()
    apply(client, posting["slug"], files={"resume": ("cv.pdf", PDF, "application/pdf")})
    folder = data_dir / "applications" / f"{posting['id']:05d}"
    assert any(folder.iterdir())
    assert client.delete(f"/api/admin/careers/postings/{posting['id']}", headers=admin).status_code == 204
    assert not any(folder.iterdir())
    assert client.get(f"/api/admin/careers/applications?posting_id={posting['id']}", headers=admin).json() == []
