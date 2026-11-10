"""Настройки бота, текущие цены и журнал изменений.

Всё хранится в backend/var/ — эта папка не попадает в git. Файлы доступны только владельцу (права 600).
"""

import json
import os
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from app.bot.strategy import Rule

VAR_DIR = Path(__file__).resolve().parents[2] / "var"
STATE_FILE = VAR_DIR / "bot_state.json"
LOG_FILE = VAR_DIR / "bot_log.jsonl"
FEED_FILE = VAR_DIR / "price.xml"
SECRET_FILE = VAR_DIR / "feed_secret"

LOG_LIMIT = 5_000  # столько последних записей журнала храним

lock = threading.RLock()


@dataclass
class ProductRule:
    enabled: bool
    min_price: int
    max_price: int
    step: int = 1
    strategy: str = "first"
    protect: bool = True  # не опускать цену ниже «без убытка», даже если минимум ниже

    def to_rule(self) -> Rule:
        return Rule(self.min_price, self.max_price, 1, self.strategy)  # шаг всегда 1 ₸  # type: ignore[arg-type]


@dataclass
class BotState:
    enabled: bool = False  # общий выключатель: False — бот ничего не делает
    dry_run: bool = True  # режим проверки: бот пишет в журнал, что сделал бы, но цены не меняет
    rules: dict[str, ProductRule] = field(default_factory=dict)  # product_id -> правило
    prices: dict[str, int] = field(default_factory=dict)  # product_id -> цена, которую отдаём в Kaspi
    last_run: str | None = None
    night_pause: bool = True  # ночью (23:00–07:00) цену не снижать
    # product_id -> ходы бота за последние сутки: [{"t": время, "up": подъём?}] — для тормозов
    moves: dict[str, list[dict]] = field(default_factory=dict)
    # product_id -> последнее решение: {"time", "price", "kind", "reason"} — «почему бот так решил»
    last: dict[str, dict] = field(default_factory=dict)


def _ensure_dir() -> None:
    VAR_DIR.mkdir(mode=0o700, exist_ok=True)


def _write_private(path: Path, text: str) -> None:
    """Атомарная запись: сначала во временный файл, потом подмена. Права — только владелец."""
    _ensure_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _state_file(shop: str) -> Path:
    """У каждого магазина свои настройки бота. Демо — в var/, настоящий магазин — в var/shops/<магазин>/."""
    return STATE_FILE if shop == "demo" else VAR_DIR / "shops" / shop / "bot_state.json"


def _log_file(shop: str) -> Path:
    return LOG_FILE if shop == "demo" else VAR_DIR / "shops" / shop / "bot_log.jsonl"


def load_state(shop: str = "demo") -> BotState:
    with lock:
        path = _state_file(shop)
        if not path.exists():
            return BotState()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BotState(
            enabled=raw.get("enabled", False),
            dry_run=raw.get("dry_run", True),
            rules={pid: ProductRule(**r) for pid, r in raw.get("rules", {}).items()},
            prices={pid: int(p) for pid, p in raw.get("prices", {}).items()},
            last_run=raw.get("last_run"),
            night_pause=raw.get("night_pause", True),
            moves=raw.get("moves", {}),
            last=raw.get("last", {}),
        )


def save_state(state: BotState, shop: str = "demo") -> None:
    with lock:
        path = _state_file(shop)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _write_private(path, json.dumps(asdict(state), ensure_ascii=False, indent=2))


def append_log(entries: list[dict], shop: str = "demo") -> None:
    if not entries:
        return
    with lock:
        path = _log_file(shop)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        lines += [json.dumps(e, ensure_ascii=False) for e in entries]
        _write_private(path, "\n".join(lines[-LOG_LIMIT:]) + "\n")


def read_log(limit: int = 200, shop: str = "demo") -> list[dict]:
    with lock:
        path = _log_file(shop)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in reversed(lines[-limit:])]


def write_feed(xml: str) -> None:
    with lock:
        _write_private(FEED_FILE, xml)


def read_feed() -> str | None:
    with lock:
        return FEED_FILE.read_text(encoding="utf-8") if FEED_FILE.exists() else None


def feed_secret() -> str:
    """Секретная часть ссылки на прайс-лист. Создаётся один раз, хранится в var/feed_secret."""
    env = os.environ.get("KASPI_FEED_SECRET", "").strip()
    if len(env) >= 32:
        return env
    with lock:
        if SECRET_FILE.exists():
            return SECRET_FILE.read_text(encoding="utf-8").strip()
        value = secrets.token_urlsafe(32)
        _write_private(SECRET_FILE, value)
        return value


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
