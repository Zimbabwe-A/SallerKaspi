"""Закупочные цены таблицей: выгрузка в Excel и загрузка обратно."""

import io

import pytest
from fastapi.testclient import TestClient

from app.routers.costs import parse_money
from app.xlsx import read_table, write_xlsx

ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import economics
    monkeypatch.setattr(economics, "shop_dir", lambda shop: tmp_path / shop)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_xlsx_round_trip():
    data = write_xlsx([["Артикул", "Название", "Закупка, ₸"], ["EL-1", "Мышь <b>&", 1500], ["EL-2", "Кабель", None]])
    assert read_table(data, "x.xlsx") == [["Артикул", "Название", "Закупка, ₸"], ["EL-1", "Мышь <b>&", "1500"], ["EL-2", "Кабель"]]


def test_csv_semicolon_and_cp1251():
    rows = read_table("Артикул;Закупка\nEL-1;1 500\n".encode("cp1251"), "x.csv")
    assert rows == [["Артикул", "Закупка"], ["EL-1", "1 500"]]


def test_parse_money_formats():
    assert parse_money("6 000") == 6000
    assert parse_money("6000,6") == 6001
    assert parse_money("6 000 ₸") == 6000
    assert parse_money("1.234.50") == 1235
    assert parse_money("") is None
    with pytest.raises(ValueError):
        parse_money("-5")


def test_export_then_import_updates_costs(client):
    from app.data.store import get_dataset
    ds = get_dataset("demo")
    exported = client.get("/api/costs/export.xlsx?shop=demo")
    assert exported.status_code == 200 and exported.content.startswith(b"PK")
    rows = read_table(exported.content)
    assert rows[0][0] == "Артикул" and len(rows) == len(ds.products) + 1
    first, second = rows[1][0], rows[2][0]
    table = write_xlsx([["Код товара", "Себестоимость"], [first, "1 234"], [second, ""], ["НЕТ-ТАКОГО", 10], [rows[3][0], "abc"]])
    r = client.post("/api/costs/import?shop=demo", files={"file": ("z.xlsx", table)}, headers=ORIGIN)
    body = r.json()
    assert r.status_code == 200, body
    assert body["updated"] == 1 and body["empty"] == 1 and body["unknown"] == ["НЕТ-ТАКОГО"] and len(body["errors"]) == 1
    from app import economics
    assert economics.load_costs("demo")[first] == 1234


def test_import_rejects_foreign_site_and_garbage(client):
    assert client.post("/api/costs/import?shop=demo", files={"file": ("z.csv", b"a;b")},
                       headers={"Origin": "https://evil.example"}).status_code == 403
    r = client.post("/api/costs/import?shop=demo", files={"file": ("z.csv", "Артикул;Закупка\nNOPE;5\n".encode())}, headers=ORIGIN)
    assert r.status_code == 400 and "не совпал" in r.json()["detail"]
