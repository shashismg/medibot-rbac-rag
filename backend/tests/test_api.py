"""API contract & server-side RBAC. The pipeline is stubbed so these tests need no models/LLM;
what matters is that the role comes from the token, not the request body."""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.schemas import ChatResponse


@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake_answer(question, role):
        calls.append((question, role))
        return ChatResponse(answer="ok", sources=[], retrieval_type="hybrid_rag", role=role)

    monkeypatch.setattr(main, "answer_question", fake_answer)
    main.app.router.lifespan_context = _no_lifespan  # skip model warm-up
    with TestClient(main.app) as c:
        c.calls = calls
        yield c


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _no_lifespan(_):
    yield


def _login(c, u, p):
    r = c.post("/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(
    "user,pw,role",
    [
        ("dr.mehta", "doctor123", "doctor"),
        ("nurse.priya", "nurse123", "nurse"),
        ("billing.ravi", "billing123", "billing_executive"),
        ("tech.anand", "tech123", "technician"),
        ("admin.sys", "admin123", "admin"),
    ],
)
def test_login_returns_role_tagged_token(client, user, pw, role):
    data = _login(client, user, pw)
    assert data["role"] == role and data["access_token"]


def test_bad_password(client):
    assert client.post("/login", json={"username": "nurse.priya", "password": "nope"}).status_code == 401


def test_chat_requires_token(client):
    assert client.post("/chat", json={"question": "hi"}).status_code == 401
    assert client.post("/chat", json={"question": "hi"}, headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_body_role_is_ignored(client):
    tok = _login(client, "nurse.priya", "nurse123")["access_token"]
    r = client.post("/chat", json={"question": "billing codes", "role": "admin"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["role"] == "nurse"
    assert client.calls[-1] == ("billing codes", "nurse")


def test_forged_token_rejected(client):
    import jwt

    forged = jwt.encode({"sub": "nurse.priya", "role": "admin"}, "wrong-secret", algorithm="HS256")
    r = client.post("/chat", json={"question": "x"}, headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_collections_endpoint(client):
    r = client.get("/collections/technician").json()
    assert r == {"role": "technician", "collections": ["general", "equipment"], "can_use_sql": False}
    assert client.get("/collections/hacker").status_code == 404
