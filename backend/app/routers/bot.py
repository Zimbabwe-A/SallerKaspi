"""API бота цен для сайта. Работает только на этом компьютере (127.0.0.1)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from app import config, economics
from app.bot import runner, storage
from app.bot.sources import TestCompetitorSource
from app.bot.strategy import decide, position
from app.deps import DatasetDep
from app.services.market import market_day


def same_site_only(request: Request) -> None:
    """Изменения принимаем только со страниц нашего сайта.

    Защищает от чужих сайтов, открытых в том же браузере: они не смогут включить бота
    или поменять цены, отправив запрос на localhost.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin not in config.CORS_ORIGINS:
        raise HTTPException(status_code=403, detail="Запрос не с сайта аналитики")
    if request.method in ("POST", "PUT") and request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(status_code=415, detail="Нужен JSON")


router = APIRouter(prefix="/bot", tags=["Бот цен"])
write = APIRouter(prefix="/bot", tags=["Бот цен"], dependencies=[Depends(same_site_only)])


class RuleIn(BaseModel):
    enabled: bool
    min_price: Annotated[int, Field(gt=0, le=100_000_000)]
    max_price: Annotated[int, Field(gt=0, le=100_000_000)]
    step: Annotated[int, Field(ge=1, le=1)] = 1  # бот всегда снижает на 1 ₸
    strategy: Literal["first", "second"] = "first"
    protect: bool = True  # не ниже цены без убытка

    @model_validator(mode="after")
    def check_range(self):
        if self.max_price < self.min_price:
            raise ValueError("Максимум должен быть не меньше минимума")
        return self


class BotRow(BaseModel):
    product_id: int
    sku: str
    name: str
    price: int
    min_competitor: int | None
    sellers: int
    rule: RuleIn | None
    position: int  # место сейчас
    next_price: int | None
    next_position: int | None  # место после пересчёта
    next_kind: Literal["target", "min", "max", "alone"] | None
    next_reason: str | None
    cost: int | None  # закупка, ₸ (None — не указана)
    break_even: int | None  # цена, ниже которой продажа в минус
    profit_now: int | None  # прибыль с 1 продажи по текущей цене
    next_profit: int | None  # прибыль с 1 продажи по цене бота
    first_place_price: int | None  # какая цена нужна, чтобы быть 1-м
    first_place_profit: int | None  # прибыль с продажи по этой цене


class BotCounts(BaseModel):
    total: int  # всего товаров
    in_bot: int  # включены в бота
    first: int  # из включённых: будут на 1-м месте
    second: int  # из включённых: будут на 2-м месте
    at_min: int  # из включённых: упёрлись в минимум и не на 1-м месте
    at_max: int  # из включённых: стоят на максимуме


class BotStatus(BaseModel):
    enabled: bool
    dry_run: bool
    last_run: str | None
    interval_seconds: int
    source: str
    feed_path: str
    feed_ready: bool
    counts: BotCounts
    rows: list[BotRow]


class SwitchIn(BaseModel):
    enabled: bool
    dry_run: bool


def _demo_only(ds) -> None:
    """Без настоящих цен конкурентов бот на настоящем магазине опасен: поднял бы всё до максимума."""
    if not ds.market_known:
        raise HTTPException(status_code=409, detail="Для настоящего магазина бот заработает, когда подключим "
                                                    "цены конкурентов с kaspi.kz. Сейчас он работает на демо-магазине.")


def _status(ds) -> BotStatus:
    _demo_only(ds)
    state = storage.load_state()
    source = TestCompetitorSource(ds)
    rows: list[BotRow] = []
    for p in ds.products.values():
        competitors = source.prices(p.id)
        rule = state.rules.get(str(p.id))
        effective, floor = runner.effective_rule(ds, p.id, rule) if rule else (None, None)
        decision = decide(effective, competitors) if rule and rule.enabled else None
        price = runner.current_price(ds, state, p.id)
        cost = economics.cost_of(ds, p)
        if floor is None and cost is not None:
            floor = economics.break_even(ds, p, cost)
        profit = (lambda value: economics.sale(ds, p, value, cost).profit) if cost is not None else (lambda value: None)
        first_price = min(competitors) - 1 if competitors else None
        reason = decision.reason if decision else None
        if decision and rule and rule.protect and floor and decision.kind == "min" and floor > rule.min_price:
            reason = f"Ниже {floor} ₸ продажа в минус — держим цену без убытка (ваш минимум {rule.min_price} ₸ ниже)"
        rows.append(BotRow(
            product_id=p.id, sku=p.sku, name=p.name,
            price=price,
            min_competitor=min(competitors) if competitors else None,
            sellers=len(competitors) + 1,
            rule=RuleIn(**{**rule.__dict__, "step": 1}) if rule else None,
            position=position(price, competitors),
            next_price=decision.price if decision else None,
            next_position=position(decision.price, competitors) if decision else None,
            next_kind=decision.kind if decision else None,
            next_reason=reason,
            cost=cost,
            break_even=floor,
            profit_now=profit(price),
            next_profit=profit(decision.price) if decision else None,
            first_place_price=first_price if first_price and first_price > 0 else None,
            first_place_profit=profit(first_price) if first_price and first_price > 0 else None,
        ))
    active = [r for r in rows if r.next_position is not None]
    counts = BotCounts(
        total=len(rows),
        in_bot=len(active),
        first=sum(r.next_position == 1 for r in active),
        second=sum(r.next_position == 2 for r in active),
        at_min=sum(r.next_kind == "min" and r.next_position != 1 for r in active),
        at_max=sum(r.next_kind == "max" for r in active),
    )
    return BotStatus(
        enabled=state.enabled, dry_run=state.dry_run, last_run=state.last_run,
        interval_seconds=config.BOT_INTERVAL_SECONDS, source=source.name,
        # Секретную часть ссылки сайт не получает: её видно только в терминале при запуске.
        feed_path="/kaspi/<секрет>/price.xml",
        feed_ready=storage.read_feed() is not None,
        counts=counts,
        rows=rows,
    )


@router.get("", response_model=BotStatus, summary="Состояние бота и товары")
def get_bot(ds: DatasetDep):
    return _status(ds)


@router.get("/log", summary="Журнал изменений цен")
def get_log(limit: int = 200):
    return storage.read_log(min(max(limit, 1), 1000))


@write.put("/products/{product_id}", response_model=BotStatus, summary="Правило для товара")
def put_rule(ds: DatasetDep, product_id: int, body: RuleIn):
    _demo_only(ds)
    if product_id not in ds.products:
        raise HTTPException(status_code=404, detail="Товар не найден")
    with storage.lock:
        state = storage.load_state()
        state.rules[str(product_id)] = storage.ProductRule(**body.model_dump())
        storage.save_state(state)
    return _status(ds)


@write.delete("/products/{product_id}", response_model=BotStatus, summary="Убрать товар из бота")
def delete_rule(ds: DatasetDep, product_id: int):
    with storage.lock:
        state = storage.load_state()
        state.rules.pop(str(product_id), None)
        storage.save_state(state)
    return _status(ds)


@write.post("/switch", response_model=BotStatus, summary="Включить / выключить, режим проверки")
def switch(ds: DatasetDep, body: SwitchIn):
    with storage.lock:
        state = storage.load_state()
        state.enabled, state.dry_run = body.enabled, body.dry_run
        storage.save_state(state)
    return _status(ds)


class CostIn(BaseModel):
    cost: Annotated[int, Field(ge=0, le=100_000_000)] | None


@write.put("/products/{product_id}/cost", summary="Закупочная цена товара")
def put_cost(ds: DatasetDep, product_id: int, body: CostIn):
    """Хранится только у вас (var/shops/<магазин>/costs.json). В Kaspi ничего не отправляется."""
    if product_id not in ds.products:
        raise HTTPException(status_code=404, detail="Товар не найден")
    product = ds.products[product_id]
    economics.set_cost(ds.shop_id, product.sku, body.cost)
    cost = economics.cost_of(ds, product)
    return {"cost": cost, "break_even": economics.break_even(ds, product, cost) if cost is not None else None}


class StockIn(BaseModel):
    quantity: Annotated[int, Field(ge=0, le=10_000_000)] | None


@write.put("/products/{product_id}/stock", summary="Остаток на складе (вручную)")
def put_stock(ds: DatasetDep, product_id: int, body: StockIn):
    """Хранится только у вас (var/shops/<магазин>/stock.json). В Kaspi ничего не отправляется."""
    if product_id not in ds.products:
        raise HTTPException(status_code=404, detail="Товар не найден")
    economics.set_stock(ds.shop_id, ds.products[product_id].sku, body.quantity)
    return {"quantity": body.quantity}


@write.post("/run", summary="Пересчитать цены сейчас")
def run_now(ds: DatasetDep):
    _demo_only(ds)
    changes = runner.run_once(ds, force=True)
    return {"changes": changes, "status": _status(ds)}
