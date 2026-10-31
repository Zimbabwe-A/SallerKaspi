"""Внешняя аналитика: конкуренты на карточке, история цен, сводка по категориям."""

from datetime import date, timedelta

from app import schemas
from app.data.models import Dataset, MarketDay

ME_ID = "me"
ME_NAME = "Мой магазин"


def market_day(ds: Dataset, product_id: int, day: date | None = None) -> MarketDay:
    history = ds.market[product_id]
    if day is None:
        return history[-1]
    return history[(day - ds.start).days]


def offers(ds: Dataset, product_id: int, day: date | None = None) -> schemas.Offers:
    md = market_day(ds, product_id, day)
    entries = [(ME_ID, md.my_price)] + list(md.competitor_prices.items())
    # При равной цене мы ниже конкурента: покупатель видит нас не первыми.
    entries.sort(key=lambda e: (e[1], e[0] == ME_ID))

    result: list[schemas.Offer] = []
    for position, (seller_id, price) in enumerate(entries, start=1):
        competitor = ds.competitors.get(seller_id)
        result.append(schemas.Offer(
            seller_id=seller_id,
            seller_name=competitor.name if competitor else ME_NAME,
            is_me=seller_id == ME_ID,
            price=price,
            position=position,
            rating=competitor.rating if competitor else None,
            delivery_days=competitor.delivery_days if competitor else None,
        ))

    me = next(o for o in result if o.is_me)
    min_price = result[0].price
    gap = me.price - min_price
    return schemas.Offers(
        product_id=product_id,
        date=md.day,
        my_price=me.price,
        my_position=me.position,
        sellers=len(result),
        min_price=min_price,
        gap_to_min=gap,
        gap_to_min_pct=round(gap / min_price * 100, 1),
        offers=result,
    )


def price_history(ds: Dataset, product_id: int, start: date, end: date) -> schemas.PriceHistory:
    points: list[schemas.PricePoint] = []
    for md in ds.market[product_id]:
        if not start <= md.day <= end:
            continue
        prices = list(md.competitor_prices.values()) + [md.my_price]
        points.append(schemas.PricePoint(
            date=md.day,
            my_price=md.my_price,
            min_price=min(prices),
            avg_price=round(sum(prices) / len(prices)),
            max_price=max(prices),
            rating=md.rating,
            reviews=md.reviews,
        ))
    return schemas.PriceHistory(product_id=product_id, period=schemas.Period(start=start, end=end), points=points)


def categories(ds: Dataset) -> list[schemas.CategoryMarket]:
    since = ds.end - timedelta(days=29)
    revenue: dict[str, int] = {cid: 0 for cid in ds.categories}
    for order in ds.orders:
        if order.day >= since:
            revenue[ds.products[order.product_id].category_id] += order.revenue

    result: list[schemas.CategoryMarket] = []
    for cid, category in ds.categories.items():
        products = [p for p in ds.products.values() if p.category_id == cid]
        indexes, sellers, cheapest = [], [], 0
        for p in products:
            md = market_day(ds, p.id)
            competitor_prices = list(md.competitor_prices.values())
            indexes.append(md.my_price / (sum(competitor_prices) / len(competitor_prices)))
            sellers.append(len(competitor_prices) + 1)
            cheapest += md.my_price < min(competitor_prices)
        result.append(schemas.CategoryMarket(
            id=cid,
            name=category.name,
            products=len(products),
            avg_sellers=round(sum(sellers) / len(sellers), 1),
            price_index=round(sum(indexes) / len(indexes) * 100, 1),
            cheapest_share=round(cheapest / len(products) * 100, 1),
            revenue_30d=revenue[cid],
        ))
    return result
