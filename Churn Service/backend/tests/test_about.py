"""About page: company profile and team members, public read and admin write."""

import pytest
from conftest import register

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(scope="module")
def admin(client):
    from app.db import session_factory
    from app.models import User

    headers = register(client, email="about-admin@example.com", org="About Ops")
    with session_factory()() as db:
        db.query(User).filter(User.email == "about-admin@example.com").update({User.is_admin: True})
        db.commit()
    return headers


def member(**fields):
    return {"name": "Ada Lovelace", "title": "CEO", "team": "leadership", "bio": "Founder.", **fields}


def test_public_about_has_default_profile(client):
    body = client.get("/api/about").json()
    assert body["profile"]["headline"] and len(body["profile"]["values"]) == 4
    assert isinstance(body["members"], list)


def test_only_admins_edit(client, admin):
    customer = register(client, email="about-customer@example.com", org="Customer Co")
    assert client.put("/api/admin/about/profile", json={"headline": "x"}).status_code == 401
    assert client.put("/api/admin/about/profile", json={"headline": "x"}, headers=customer).status_code == 403
    assert client.post("/api/admin/about/members", json=member(), headers=customer).status_code == 403


def test_update_profile(client, admin):
    body = {"headline": "Hello", "intro": "Intro", "mission": "Mission", "story": "One.\n\nTwo.", "founded": "2024",
            "headquarters": "Remote", "contact_email": "Hello@WSL.example.com", "linkedin_url": "linkedin.com/company/wsl",
            "github_url": "", "values": [{"title": "Care", "text": "We care."}, {"title": "  ", "text": "dropped"}]}
    saved = client.put("/api/admin/about/profile", json=body, headers=admin).json()
    assert saved["contact_email"] == "hello@wsl.example.com" and saved["linkedin_url"] == "https://linkedin.com/company/wsl"
    assert saved["values"] == [{"title": "Care", "text": "We care."}]
    assert client.get("/api/about").json()["profile"]["headline"] == "Hello"
    assert client.put("/api/admin/about/profile", json={**body, "contact_email": "nope"}, headers=admin).status_code == 422
    assert client.put("/api/admin/about/profile", json={**body, "contact_email": ""}, headers=admin).json()["contact_email"] == ""


def test_members_crud_order_and_visibility(client, admin):
    ceo = client.post("/api/admin/about/members", json=member(), headers=admin).json()
    cto = client.post("/api/admin/about/members", json=member(name="Alan Turing", title="CTO"), headers=admin).json()
    eng = client.post("/api/admin/about/members", json=member(name="Grace Hopper", title="Engineer", team="engineering",
                                                              github_url="github.com/grace"), headers=admin).json()
    assert eng["github_url"] == "https://github.com/grace"
    names = [m["name"] for m in client.get("/api/about").json()["members"]]
    assert names.index("Ada Lovelace") < names.index("Alan Turing") < names.index("Grace Hopper")  # leadership first

    client.put("/api/admin/about/members/order", json={"ids": [cto["id"], ceo["id"]]}, headers=admin)
    names = [m["name"] for m in client.get("/api/about").json()["members"]]
    assert names.index("Alan Turing") < names.index("Ada Lovelace")

    client.put(f"/api/admin/about/members/{eng['id']}", json=member(name="Grace Hopper", title="Engineer", team="engineering",
                                                                     visible=False), headers=admin)
    assert "Grace Hopper" not in [m["name"] for m in client.get("/api/about").json()["members"]]
    assert "Grace Hopper" in [m["name"] for m in client.get("/api/admin/about/members", headers=admin).json()]

    assert client.post("/api/admin/about/members", json=member(team="sales"), headers=admin).status_code == 422
    assert client.delete(f"/api/admin/about/members/{eng['id']}", headers=admin).status_code == 204
    assert client.put(f"/api/admin/about/members/{eng['id']}", json=member(), headers=admin).status_code == 404


def test_photos(client, admin, data_dir):
    m = client.post("/api/admin/about/members", json=member(name="Photo Person"), headers=admin).json()
    url = f"/api/admin/about/members/{m['id']}/photo"
    assert m["photo_url"] is None
    up = client.post(url, files={"photo": ("me.png", PNG, "image/png")}, headers=admin).json()
    assert up["photo_url"].startswith(f"/api/about/photos/{m['id']}")
    served = client.get(up["photo_url"])
    assert served.status_code == 200 and served.content == PNG and served.headers["content-type"] == "image/png"

    # replacing removes the old file; stored names are random
    again = client.post(url, files={"photo": ("me.jpeg", JPG, "image/jpeg")}, headers=admin).json()
    assert again["photo_url"] != up["photo_url"]
    files = list((data_dir / "team").iterdir())
    assert len([f for f in files if f.suffix in (".png", ".jpg")]) >= 1 and all("me" not in f.stem for f in files)

    assert client.post(url, files={"photo": ("x.gif", b"GIF89a", "image/gif")}, headers=admin).status_code == 422
    assert client.post(url, files={"photo": ("x.png", b"not png", "image/png")}, headers=admin).status_code == 422
    big = b"\x89PNG" + b"0" * (3 * 1024 * 1024)
    assert client.post(url, files={"photo": ("x.png", big, "image/png")}, headers=admin).status_code == 413
    assert client.post(url, files={"photo": ("x.png", PNG, "image/png")}).status_code == 401

    cleared = client.delete(url, headers=admin).json()
    assert cleared["photo_url"] is None
    assert client.get(f"/api/about/photos/{m['id']}").status_code == 404
