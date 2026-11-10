"""Аккаунты продавцов. Вход — по номеру телефона и паролю.
При регистрации ещё спрашиваем имя, почту и (необязательно) код приглашения или скидки.

Хранится в backend/var/accounts.db (SQLite). Пароль — только хэш scrypt с солью.
Сессия — случайный токен в cookie (HttpOnly), в базе лежит его SHA-256.
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

DB_PATH = Path(__file__).resolve().parents[1] / "var" / "accounts.db"
COOKIE = "sk_session"
SESSION_DAYS = 30

CODE_TTL = 5 * 60  # код из SMS действует 5 минут
RESEND_AFTER = 60  # отправить код ещё раз — не чаще раза в минуту
MAX_ATTEMPTS = 5  # после 5 неверных кодов нужно запросить новый

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/auth", tags=["Аккаунт"])


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            login TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        -- Регистрация, которая ждёт код из SMS. Аккаунт появляется только после кода.
        CREATE TABLE IF NOT EXISTS pending (
            phone TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            sent_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            test_code TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
        -- Какие накладные аккаунт уже печатал: только номер накладной или отпечаток страницы,
        -- без имён и адресов покупателей. Нужно, чтобы не печатать одну накладную дважды.
        CREATE TABLE IF NOT EXISTS printed_waybills (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            printed_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, key)
        );
        """
    )
    # Какие настоящие магазины видит аккаунт (через запятую). Демо видят все.
    if "test_code" not in {r["name"] for r in conn.execute("PRAGMA table_info(pending)")}:
        conn.execute("ALTER TABLE pending ADD COLUMN test_code TEXT NOT NULL DEFAULT ''")
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if "shops" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN shops TEXT NOT NULL DEFAULT ''")
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email)")
    if "promo_code" not in columns:
        # Код приглашения или скидки, который ввели при регистрации. Пока только сохраняем.
        conn.execute("ALTER TABLE users ADD COLUMN promo_code TEXT NOT NULL DEFAULT ''")
    return conn


# ---------- телефон и почта ----------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw: str) -> str:
    """Телефон приводим к +7XXXXXXXXXX: «8 771…», «+7 (771)…» и «771…» — один номер."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        raise HTTPException(422, "Введите номер полностью: +7 (___) ___ ____")
    return "+7" + digits


def normalize_email(raw: str) -> str:
    value = raw.strip().lower()
    if not EMAIL_RE.match(value):
        raise HTTPException(422, "Проверьте адрес почты")
    return value


# ---------- пароли ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- SMS ----------

def sms_connected() -> bool:
    """SMS-сервис ещё не подключён: код пишется в журнал сервера и показывается на странице."""
    return False


def send_sms(phone: str, text: str) -> None:
    """Сюда подключается SMS-сервис (например, Mobizon или SMSC.kz). Пока — только журнал."""
    log.warning("SMS на %s: %s", phone, text)


def _code_hash(phone: str, code: str) -> str:
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _send_code(conn: sqlite3.Connection, phone: str) -> dict:
    code = f"{secrets.randbelow(10_000):04d}"
    now = int(time.time())
    # Пока SMS не подключены, код хранится открыто, чтобы показать его на странице.
    test_code = "" if sms_connected() else code
    conn.execute(
        "UPDATE pending SET code_hash = ?, expires_at = ?, sent_at = ?, attempts = 0, test_code = ? WHERE phone = ?",
        (_code_hash(phone, code), now + CODE_TTL, now, test_code, phone),
    )
    conn.commit()
    send_sms(phone, f"Код для регистрации в Аналитике Kaspi: {code}")
    return _code_info(phone, now, test_code)


def _code_info(phone: str, sent_at: int, test_code: str) -> dict:
    now = int(time.time())
    result = {"phone": phone, "resend_in": max(0, RESEND_AFTER - (now - sent_at)),
              "expires_in": max(0, CODE_TTL - (now - sent_at))}
    if test_code:
        result["test_code"] = test_code
    return result


# ---------- сессии ----------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn: sqlite3.Connection, user_id: int, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, int(time.time()) + SESSION_DAYS * 86400),
    )
    conn.commit()
    response.set_cookie(
        COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/",
    )


# Пропуск уже напечатанных накладных — пока только у аккаунтов с настоящим магазином (владелец).
WAYBILL_HISTORY_SHOP = "main"


def _public(row: sqlite3.Row) -> dict:
    shops = [s for s in row["shops"].split(",") if s]
    features = ["waybill_history"] if WAYBILL_HISTORY_SHOP in shops else []
    return {"id": row["id"], "login": row["login"], "phone": row["login"], "email": row["email"], "name": row["name"],
            "shops": shops, "features": features}


# ---------- уже напечатанные накладные ----------
PRINTED_KEEP_DAYS = 120


def printed_keys(user_id: int) -> set[str]:
    with _db() as conn:
        return {r["key"] for r in conn.execute("SELECT key FROM printed_waybills WHERE user_id = ?", (user_id,))}


def remember_printed(user_id: int, keys: list[str]) -> None:
    now = int(time.time())
    with _db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO printed_waybills (user_id, key, printed_at) VALUES (?, ?, ?)",
            [(user_id, k, now) for k in keys],
        )
        conn.execute("DELETE FROM printed_waybills WHERE printed_at < ?", (now - PRINTED_KEEP_DAYS * 86400,))


def current_user(token: str | None) -> dict | None:
    if not token:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = ? AND s.expires_at > ?",
            (_token_hash(token), int(time.time())),
        ).fetchone()
    return _public(row) if row else None


def grant(phone: str, shop: str) -> None:
    """Открыть аккаунту настоящий магазин. Запуск: python -m app.auth grant <телефон> <магазин>."""
    login_value = normalize_phone(phone)
    with _db() as conn:
        row = conn.execute("SELECT shops FROM users WHERE login = ?", (login_value,)).fetchone()
        if not row:
            raise SystemExit(f"Нет аккаунта {login_value}")
        shops = [s for s in row["shops"].split(",") if s]
        if shop not in shops:
            shops.append(shop)
        conn.execute("UPDATE users SET shops = ? WHERE login = ?", (",".join(shops), login_value))
    print(f"{login_value}: магазины {', '.join(['demo', *shops])}")


# ---------- API ----------

class RegisterBody(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    code: str = ""


class LoginBody(BaseModel):
    phone: str
    password: str


SessionCookie = Annotated[str | None, Cookie(alias=COOKIE)]


class PhoneBody(BaseModel):
    phone: str


class VerifyBody(BaseModel):
    phone: str
    code: str


@router.post("/register/start", summary="Регистрация, шаг 1: проверить данные и отправить код в SMS")
def register_start(body: RegisterBody):
    name = body.name.strip()[:80]
    if not name:
        raise HTTPException(422, "Укажите имя")
    email = normalize_email(body.email)
    phone = normalize_phone(body.phone)
    if len(body.password) < 8:
        raise HTTPException(422, "Пароль — не короче 8 символов")
    with _db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE login = ?", (phone,)).fetchone():
            raise HTTPException(409, "С этим номером уже есть аккаунт — войдите")
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "Эта почта уже занята")
        data = {"name": name, "email": email, "promo_code": body.code.strip().upper()[:40],
                "password_hash": hash_password(body.password)}
        old = conn.execute("SELECT * FROM pending WHERE phone = ?", (phone,)).fetchone()
        if old and time.time() - old["sent_at"] < RESEND_AFTER:
            # Вернулись исправить данные и снова нажали «Далее» — код тот же, новый SMS не шлём.
            conn.execute("UPDATE pending SET data = ? WHERE phone = ?", (json.dumps(data, ensure_ascii=False), phone))
            return _code_info(phone, old["sent_at"], old["test_code"])
        conn.execute(
            "INSERT OR REPLACE INTO pending (phone, data, code_hash, expires_at, sent_at) VALUES (?, ?, '', 0, 0)",
            (phone, json.dumps(data, ensure_ascii=False)),
        )
        return _send_code(conn, phone)


@router.post("/register/resend", summary="Отправить код ещё раз")
def register_resend(body: PhoneBody):
    phone = normalize_phone(body.phone)
    with _db() as conn:
        row = conn.execute("SELECT sent_at FROM pending WHERE phone = ?", (phone,)).fetchone()
        if not row:
            raise HTTPException(404, "Начните регистрацию заново")
        wait = RESEND_AFTER - int(time.time() - row["sent_at"])
        if wait > 0:
            raise HTTPException(429, f"Отправить ещё раз можно через {wait} с")
        return _send_code(conn, phone)


@router.post("/register/verify", summary="Регистрация, шаг 2: код из SMS → аккаунт")
def register_verify(body: VerifyBody, response: Response):
    phone = normalize_phone(body.phone)
    with _db() as conn:
        row = conn.execute("SELECT * FROM pending WHERE phone = ?", (phone,)).fetchone()
        if not row:
            raise HTTPException(404, "Начните регистрацию заново")
        if row["expires_at"] < time.time():
            raise HTTPException(410, "Код устарел — отправьте новый")
        if row["attempts"] >= MAX_ATTEMPTS:
            raise HTTPException(429, "Слишком много попыток — отправьте новый код")
        if not hmac.compare_digest(_code_hash(phone, body.code.strip()), row["code_hash"]):
            conn.execute("UPDATE pending SET attempts = attempts + 1 WHERE phone = ?", (phone,))
            conn.commit()
            left = MAX_ATTEMPTS - row["attempts"] - 1
            raise HTTPException(400, f"Неверный код. Осталось попыток: {left}" if left else "Неверный код — отправьте новый")
        data = json.loads(row["data"])
        if conn.execute("SELECT 1 FROM users WHERE login = ? OR email = ?", (phone, data["email"])).fetchone():
            raise HTTPException(409, "Номер или почта уже заняты — войдите")
        cur = conn.execute(
            "INSERT INTO users (login, kind, name, email, promo_code, password_hash, created_at)"
            " VALUES (?, 'phone', ?, ?, ?, ?, ?)",
            (phone, data["name"], data["email"], data["promo_code"], data["password_hash"], int(time.time())),
        )
        conn.execute("DELETE FROM pending WHERE phone = ?", (phone,))
        _start_session(conn, cur.lastrowid, response)
        user = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(user)


@router.post("/login", summary="Войти")
def login(body: LoginBody, response: Response):
    phone = normalize_phone(body.phone)
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE login = ?", (phone,)).fetchone()
        if not row or not check_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Неверный номер или пароль")
        _start_session(conn, row["id"], response)
    return _public(row)


@router.post("/logout", summary="Выйти")
def logout(response: Response, sk_session: SessionCookie = None):
    if sk_session:
        with _db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(sk_session),))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me", summary="Кто вошёл")
def me(sk_session: SessionCookie = None):
    user = current_user(sk_session)
    if not user:
        raise HTTPException(401, "Не выполнен вход")
    return user


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "grant":
        grant(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("python -m app.auth grant <телефон> <магазин>")
