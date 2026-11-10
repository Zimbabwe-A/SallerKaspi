"""Аккаунты: регистрация в 2 шага (данные → код из SMS) и вход только по телефону."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth

NEW = {"name": "Айгерим", "email": "Seller@Mail.kz", "phone": "8 (701) 234-56-78", "password": "secret123", "code": "start10"}


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "accounts.db")
    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    return TestClient(app)


def register(c, body=NEW):
    sent = c.post("/api/auth/register/start", json=body).json()
    return c.post("/api/auth/register/verify", json={"phone": body["phone"], "code": sent["test_code"]})


def test_register_with_code_then_login_by_phone(c):
    sent = c.post("/api/auth/register/start", json=NEW).json()
    assert sent["phone"] == "+77012345678" and len(sent["test_code"]) == 4
    with auth._db() as conn:  # до кода аккаунта нет
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    user = c.post("/api/auth/register/verify", json={"phone": "+77012345678", "code": sent["test_code"]}).json()
    assert user["phone"] == "+77012345678" and user["email"] == "seller@mail.kz" and user["name"] == "Айгерим"
    assert c.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.post("/api/auth/login", json={"phone": "+7 701 234 5678", "password": "bad"}).status_code == 401
    assert c.post("/api/auth/login", json={"phone": "7012345678", "password": "secret123"}).status_code == 200
    with auth._db() as conn:
        assert conn.execute("SELECT promo_code FROM users").fetchone()[0] == "START10"
        assert conn.execute("SELECT count(*) FROM pending").fetchone()[0] == 0


def test_wrong_code_limits_and_resend(c, monkeypatch):
    sent = c.post("/api/auth/register/start", json=NEW).json()
    wrong = "0000" if sent["test_code"] != "0000" else "1111"
    for _ in range(auth.MAX_ATTEMPTS):
        assert c.post("/api/auth/register/verify", json={"phone": NEW["phone"], "code": wrong}).status_code == 400
    # После 5 ошибок даже верный код не принимается.
    assert c.post("/api/auth/register/verify", json={"phone": NEW["phone"], "code": sent["test_code"]}).status_code == 429
    assert c.post("/api/auth/register/resend", json={"phone": NEW["phone"]}).status_code == 429  # минута не прошла
    # Вернулись исправить данные и снова «Далее» в ту же минуту — тот же код, без ошибки.
    again = c.post("/api/auth/register/start", json={**NEW, "name": "Айгерим Б."}).json()
    assert again["test_code"] == sent["test_code"] and 0 < again["resend_in"] <= 60
    monkeypatch.setattr(auth, "RESEND_AFTER", 0)
    again = c.post("/api/auth/register/resend", json={"phone": NEW["phone"]}).json()
    assert c.post("/api/auth/register/verify", json={"phone": NEW["phone"], "code": again["test_code"]}).status_code == 200


def test_register_checks_fields(c):
    start = lambda body: c.post("/api/auth/register/start", json=body).status_code  # noqa: E731
    assert start({**NEW, "name": " "}) == 422
    assert start({**NEW, "email": "нет"}) == 422
    assert start({**NEW, "phone": "123"}) == 422
    assert start({**NEW, "password": "short"}) == 422
    assert register(c, {**NEW, "code": ""}).status_code == 200  # код скидки необязателен
    assert start(NEW) == 409  # номер занят
    assert start({**NEW, "phone": "7010000000"}) == 409  # почта занята
