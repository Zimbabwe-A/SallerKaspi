"""XML-прайс-лист в формате Kaspi (kaspi_catalog).

Формат: guide.kaspi.kz/partner/ru/shop/goods/price_list/q2962
Важно: товары, которых нет в файле, Kaspi снимает с продажи — поэтому в файл всегда идут ВСЕ товары магазина.
"""

from dataclasses import dataclass
from datetime import datetime
from xml.sax.saxutils import escape, quoteattr


@dataclass(frozen=True)
class FeedOffer:
    sku: str
    model: str
    brand: str
    price: int
    stock: int


def build_xml(company: str, merchant_id: str, store_id: str, offers: list[FeedOffer],
              now: datetime | None = None) -> str:
    now = now or datetime.now()
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<kaspi_catalog date={quoteattr(now.strftime("%Y-%m-%d %H:%M"))} xmlns="kaspiShopping" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="kaspiShopping http://kaspi.kz/kaspishopping.xsd">',
        f"  <company>{escape(company)}</company>",
        f"  <merchantid>{escape(merchant_id)}</merchantid>",
        "  <offers>",
    ]
    for o in offers:
        available = "yes" if o.stock > 0 else "no"
        lines += [
            f"    <offer sku={quoteattr(o.sku)}>",
            f"      <model>{escape(o.model)}</model>",
            f"      <brand>{escape(o.brand)}</brand>",
            "      <availabilities>",
            f"        <availability available=\"{available}\" storeId={quoteattr(store_id)} "
            f"stockCount=\"{max(o.stock, 0)}\"/>",
            "      </availabilities>",
            f"      <price>{int(o.price)}</price>",
            "    </offer>",
        ]
    lines += ["  </offers>", "</kaspi_catalog>", ""]
    return "\n".join(lines)
