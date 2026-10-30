from app.main import app
from app.database import get_db
from app.database import Base
from app.models import User

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

PASSWORD = "password123"

def _register(client, email):
    return client.post("/auth/register", json={"email": email, "password": PASSWORD})

def _login(client, email):
    return client.post("/auth/login", data={"username": email, "password": PASSWORD})

def _auth_headers(client, email):
    r = _login(client, email)
    assert r.status_code == 200, f"login gagal: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def _make_user(client, db_session, email):
    _register(client, email)
    headers = _auth_headers(client, email)
    user = db_session.query(User).filter(User.email == email).first()
    return {"id": user.id, "email": email, "headers": headers}

@pytest.fixture
def user_a(client, db_session):
    return _make_user(client, db_session, "alice@example.com")

@pytest.fixture
def user_b(client, db_session):
    return _make_user(client, db_session, "bob@example.com")

# ============================================================
# AUTH
# ============================================================
class TestAuth:
    def test_register_success(self, client):
        r = _register(client, "new@example.com")
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "new@example.com"
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_duplicate_email(self, client):
        _register(client, "dup@example.com")
        r = _register(client, "dup@example.com")
        assert r.status_code == 400

    def test_register_normalizes_email(self, client):
        r = _register(client, "  MiXeD@Example.COM  ")
        assert r.status_code == 201
        assert r.json()["email"] == "mixed@example.com"

    def test_login_success(self, client):
        _register(client, "login@example.com")
        r = _login(client, "login@example.com")
        assert r.status_code == 200
        data = r.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]

    def test_login_wrong_password(self, client):
        _register(client, "wrong@example.com")
        r = client.post("/auth/login", data={
            "username": "wrong@example.com", "password": "salahbanget"
        })
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        r = _login(client, "nobody@example.com")
        assert r.status_code == 401


# ============================================================
# GROUPS
# ============================================================
class TestGroups:
    def test_create_group_requires_auth(self, client):
        r = client.post("/groups", json={"name": "Trip"})
        assert r.status_code == 401

    def test_create_group(self, client, user_a):
        r = client.post("/groups", json={"name": "Trip"}, headers=user_a["headers"])
        assert r.status_code == 201
        assert r.json()["name"] == "Trip"

    def test_get_my_groups(self, client, user_a):
        for name in ["G1", "G2"]:
            client.post("/groups", json={"name": name}, headers=user_a["headers"])
        r = client.get("/groups", headers=user_a["headers"])
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_invite_member_success(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        r = client.post(
            f"/groups/{g['id']}/invite",
            json={"email": user_b["email"]},
            headers=user_a["headers"],
        )
        assert r.status_code == 200

    def test_invite_unknown_user(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        r = client.post(
            f"/groups/{g['id']}/invite",
            json={"email": "nobody@example.com"},
            headers=user_a["headers"],
        )
        assert r.status_code == 404

    def test_invite_duplicate_member(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        assert r.status_code == 400

    def test_invite_requires_admin(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        _register(client, "charlie@example.com")
        r = client.post(
            f"/groups/{g['id']}/invite",
            json={"email": "charlie@example.com"},
            headers=user_b["headers"],
        )
        assert r.status_code == 403

    def test_get_members(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.get(f"/groups/{g['id']}/members", headers=user_a["headers"])
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_admin_can_remove_member(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.delete(f"/groups/{g['id']}/members/{user_b['id']}", headers=user_a["headers"])
        assert r.status_code == 200

    def test_member_can_leave(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.delete(f"/groups/{g['id']}/members/{user_b['id']}", headers=user_b["headers"])
        assert r.status_code == 200

    def test_cannot_remove_last_admin(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        r = client.delete(f"/groups/{g['id']}/members/{user_a['id']}", headers=user_a["headers"])
        assert r.status_code == 400

    def test_member_cannot_remove_others(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        _register(client, "charlie@example.com")
        client.post(f"/groups/{g['id']}/invite", json={"email": "charlie@example.com"}, headers=user_a["headers"])
        members = client.get(f"/groups/{g['id']}/members", headers=user_a["headers"]).json()
        charlie_id = next(m["user_id"] for m in members if m["email"] == "charlie@example.com")
        r = client.delete(f"/groups/{g['id']}/members/{charlie_id}", headers=user_b["headers"])
        assert r.status_code == 403

    def test_promote_member(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.patch(f"/groups/{g['id']}/members/{user_b['id']}/promote", headers=user_a["headers"])
        assert r.status_code == 200
        members = client.get(f"/groups/{g['id']}/members", headers=user_a["headers"]).json()
        bob = next(m for m in members if m["email"] == user_b["email"])
        assert bob["role"] == "admin"

    def test_promote_already_admin(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        r = client.patch(f"/groups/{g['id']}/members/{user_a['id']}/promote", headers=user_a["headers"])
        assert r.status_code == 400

    def test_promote_requires_admin(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        r = client.patch(f"/groups/{g['id']}/members/{user_a['id']}/promote", headers=user_b["headers"])
        assert r.status_code == 403


# ============================================================
# EXPENSES
# ============================================================
class TestExpenses:
    def _group_with_members(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(f"/groups/{g['id']}/invite", json={"email": user_b["email"]}, headers=user_a["headers"])
        return g

    def test_create_expense_success(self, client, user_a, user_b):
        g = self._group_with_members(client, user_a, user_b)
        payload = {
            "description": "Dinner",
            "amount": 100.0,
            "paid_by": user_a["id"],
            "splits": [
                {"user_id": user_a["id"], "amount": 50.0},
                {"user_id": user_b["id"], "amount": 50.0},
            ],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 201
        data = r.json()
        assert data["description"] == "Dinner"
        assert float(data["amount"]) == 100.0

    def test_create_expense_empty_splits(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {"description": "X", "amount": 10.0, "paid_by": user_a["id"], "splits": []}
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_non_positive_amount(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 0, "paid_by": user_a["id"],
            "splits": [{"user_id": user_a["id"], "amount": 0}],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_paid_by_other(self, client, user_a, user_b):
        g = self._group_with_members(client, user_a, user_b)
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_b["id"],
            "splits": [{"user_id": user_a["id"], "amount": 10.0}],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 403

    def test_create_expense_duplicate_users(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_a["id"],
            "splits": [
                {"user_id": user_a["id"], "amount": 5.0},
                {"user_id": user_a["id"], "amount": 5.0},
            ],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_negative_split(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_a["id"],
            "splits": [{"user_id": user_a["id"], "amount": -1.0}],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_total_mismatch(self, client, user_a):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_a["id"],
            "splits": [{"user_id": user_a["id"], "amount": 5.0}],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_split_user_not_member(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_a["id"],
            "splits": [
                {"user_id": user_a["id"], "amount": 5.0},
                {"user_id": user_b["id"], "amount": 5.0},
            ],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_a["headers"])
        assert r.status_code == 400

    def test_create_expense_by_non_member(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        payload = {
            "description": "X", "amount": 10.0, "paid_by": user_b["id"],
            "splits": [{"user_id": user_b["id"], "amount": 10.0}],
        }
        r = client.post(f"/groups/{g['id']}/expenses", json=payload, headers=user_b["headers"])
        assert r.status_code in (403, 404)


class TestBalances:
    def _setup_group(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        client.post(
            f"/groups/{g['id']}/invite",
            json={"email": user_b["email"]},
            headers=user_a["headers"],
        )
        return g

    def _add_expense(self, client, user_a, user_b, group_id, amount, payer_id):
        half = amount / 2
        headers = user_a["headers"] if payer_id == user_a["id"] else user_b["headers"]

        payload = {
            "description": "X",
            "amount": amount,
            "paid_by": payer_id,
            "splits": [
                {"user_id": user_a["id"], "amount": half},
                {"user_id": user_b["id"], "amount": half},
            ],
        }
        r = client.post(
            f"/groups/{group_id}/expenses",
            json=payload,
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return r

    def _balances_dict(self, client, group_id, headers):
        r = client.get(f"/groups/{group_id}/balances", headers=headers)
        assert r.status_code == 200, r.text
        return {row["email"]: float(row["balance"]) for row in r.json()}

    def test_empty_group(self, client, user_a, user_b):
        g = self._setup_group(client, user_a, user_b)
        balances = self._balances_dict(client, g["id"], user_a["headers"])
        assert balances == {user_a["email"]: 0.0, user_b["email"]: 0.0}

    def test_after_one_expense(self, client, user_a, user_b):
        g = self._setup_group(client, user_a, user_b)
        self._add_expense(client, user_a, user_b, g["id"], amount=100.0, payer_id=user_a["id"])
        balances = self._balances_dict(client, g["id"], user_a["headers"])
        assert balances[user_a["email"]] == 50.0
        assert balances[user_b["email"]] == -50.0

    def test_net_zero_after_mutual_expenses(self, client, user_a, user_b):
        g = self._setup_group(client, user_a, user_b)
        self._add_expense(client, user_a, user_b, g["id"], amount=100.0, payer_id=user_a["id"])
        self._add_expense(client, user_a, user_b, g["id"], amount=100.0, payer_id=user_b["id"])
        balances = self._balances_dict(client, g["id"], user_a["headers"])
        assert balances[user_a["email"]] == 0.0
        assert balances[user_b["email"]] == 0.0

    def test_requires_membership(self, client, user_a, user_b):
        g = client.post("/groups", json={"name": "G"}, headers=user_a["headers"]).json()
        r = client.get(f"/groups/{g['id']}/balances", headers=user_b["headers"])
        assert r.status_code in (403, 404)

    def test_does_not_crash_after_member_removed(self, client, user_a, user_b):
        g = self._setup_group(client, user_a, user_b)
        self._add_expense(client, user_a, user_b, g["id"], amount=100.0, payer_id=user_a["id"])
        r = client.delete(
            f"/groups/{g['id']}/members/{user_b['id']}",
            headers=user_a["headers"],
        )
        assert r.status_code == 200
        balances = self._balances_dict(client, g["id"], user_a["headers"])
        assert user_b["email"] not in balances