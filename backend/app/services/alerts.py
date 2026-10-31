"""Сигналы: что изменилось на рынке и в магазине и требует внимания."""

from datetime import timedelta

from app import schemas
from app.data.models import Dataset
from app.services import internal, market

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₸"


def alerts(ds: Dataset) -> list[schemas.Alert]:
    result: list[schemas.Alert] = []
    week_ago = ds.end - timedelta(days=7)

    for product in ds.products.values():
        base = dict(product_id=product.id, sku=product.sku, product_name=product.name)
        now = market.offers(ds, product.id)
        before = market.offers(ds, product.id, week_ago)

        if before.my_position == 1 and now.my_position > 1:
            leader = now.offers[0]
            result.append(schemas.Alert(
                type="lost_lowest_price", severity="high", date=now.date, **base,
                message=f"Вы больше не самый дешёвый: {leader.seller_name} продаёт за {fmt(leader.price)}, "
                        f"ваша цена {fmt(now.my_price)}.",
            ))

        old_prices = market.market_day(ds, product.id, week_ago).competitor_prices
        current = market.market_day(ds, product.id)
        for seller_id, price in current.competitor_prices.items():
            old = old_prices.get(seller_id, price)
            if price <= old * 0.97 and price < current.my_price <= old:
                result.append(schemas.Alert(
                    type="competitor_undercut", severity="medium", date=current.day, **base,
                    message=f"{ds.competitors[seller_id].name} снизил цену с {fmt(old)} до {fmt(price)} "
                            f"— теперь дешевле вас.",
                ))

        rating_before = market.market_day(ds, product.id, week_ago).rating
        if current.rating <= rating_before - 0.05:
            result.append(schemas.Alert(
                type="rating_drop", severity="low", date=current.day, **base,
                message=f"Рейтинг снизился с {rating_before} до {current.rating} за неделю.",
            ))

        stock = internal.stock_row(ds, product)
        if stock.status in ("out", "critical"):
            text = ("Товар закончился." if stock.status == "out"
                    else f"Остатка хватит примерно на {stock.days_of_cover:g} дн.")
            if stock.incoming_date:
                text += f" Ожидается поставка {stock.incoming_quantity} шт. {stock.incoming_date:%d.%m}."
            result.append(schemas.Alert(
                type="stock_low", severity="high" if stock.status == "out" else "medium",
                date=ds.end, message=text, **base,
            ))

    return sorted(result, key=lambda a: (SEVERITY_ORDER[a.severity], -a.date.toordinal(), a.product_id))
