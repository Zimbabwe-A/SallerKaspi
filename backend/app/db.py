"""Хранилище данных, которые вводит пользователь. Тестовые данные магазина сюда не попадают."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app import config


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        with connection:
            yield connection
    finally:
        connection.close()
