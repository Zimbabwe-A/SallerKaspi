"""Накладные: пропуск уже напечатанных (только у владельца магазина)."""

import io
import time

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from app import auth
from app.routers import waybills as router
from app.waybills import build, order_number

ORIGIN = {"Origin": "http://localhost:5173"}


def waybill(mark: int) -> bytes:
    """A4-накладная с уникальным рисунком (как у разных заказов)."""
    w = PdfWriter()
    page = w.add_blank_page(width=595.275, height=841.875)
    stream = DecodedStreamObject()
    stream.set_data(f"0 0 0 rg 10 700 {mark} 50 re f".encode())
    page[NameObject("/Contents")] = w._add_object(stream)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


@pytest.fixture
def owner(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "accounts.db")
    app = FastAPI()
    app.include_router(router.router, prefix="/api")
    client = TestClient(app)

    def login(shops: str) -> TestClient:
        with auth._db() as conn:
            uid = conn.execute(
                "INSERT INTO users (login, kind, password_hash, created_at, shops) VALUES (?, 'phone', 'x', ?, ?)",
                (f"7700{shops or 'none'}{time.time_ns()}", int(time.time()), shops),
            ).lastrowid
            response = Response()
            auth._start_session(conn, uid, response)
        token = response.headers["set-cookie"].split(";")[0].split("=", 1)[1]
        client.cookies.set(auth.COOKIE, token)
        return client

    return login


def send(c, numbers, **form):
    files = [("files", (f"W_{n}.pdf", waybill(n), "application/pdf")) for n in numbers]
    return c.post("/api/waybills/merge", files=files, data={"size": "75x120", **form}, headers=ORIGIN)


def test_order_number_from_kaspi_file_names():
    assert order_number("W_1145092664.pdf") == "1145092664"
    assert order_number("W_1145092664-2.pdf") == "1145092664"
    assert order_number("waybills/W_1146886747.PDF") == "1146886747"
    assert order_number("nakladnye.pdf") is None


def test_second_print_skips_already_printed(owner):
    c = owner("main")
    first = send(c, range(1, 7))
    assert first.status_code == 200 and first.headers["X-Labels"] == "6" and first.headers["X-Skipped"] == "0"
    second = send(c, range(1, 16))
    assert second.status_code == 200 and second.headers["X-Labels"] == "9" and second.headers["X-Skipped"] == "6"
    assert len(PdfReader(io.BytesIO(second.content)).pages) == 9
    again = send(c, range(1, 16))
    assert again.status_code == 409 and "уже напечатаны" in again.json()["detail"]
    anyway = send(c, range(1, 16), skip_printed="false")
    assert anyway.status_code == 200 and anyway.headers["X-Labels"] == "15"


def test_copies_in_one_batch_print_once(owner):
    c = owner("main")
    files = [("files", (name, waybill(5), "application/pdf")) for name in ["W_5.pdf", "W_5-2.pdf", "W_5-3.pdf"]]
    r = c.post("/api/waybills/merge", files=files, data={"size": "75x120"}, headers=ORIGIN)
    assert r.headers["X-Labels"] == "1" and r.headers["X-Skipped"] == "2"


def test_same_page_without_order_number_is_recognised():
    pdf = waybill(3)
    built = build([("all.pdf", pdf)], "75x120", skip=set())
    again = build([("other-name.pdf", pdf)], "75x120", skip=set(built.keys))
    assert built.count == 1 and again.count == 0 and again.skipped == 1


def test_other_accounts_print_everything_every_time(owner):
    c = owner("")
    assert send(c, range(1, 7)).headers["X-Labels"] == "6"
    r = send(c, range(1, 7))
    assert r.headers["X-Labels"] == "6" and r.headers["X-Skipped"] == "0"
    with auth._db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM printed_waybills").fetchone()[0] == 0
