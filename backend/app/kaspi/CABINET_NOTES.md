# Кабинет продавца Kaspi — как он отдаёт товары (изучено 06.11.2026, только чтение)

Вход: `https://idmc.shop.kaspi.kz/login` (вкладки «Телефон» / «Email»), после входа — `https://kaspi.kz/mc/`.
Данные кабинет берёт с `https://mc.shop.kaspi.kz` (сессия — cookie после входа).

## Вход по почте (записано 07.11.2026, значения не сохранялись)

`POST https://idmc.shop.kaspi.kz/api/p/login`, JSON: `{"_u": почта, "_p": пароль, "_r_d": true}`
(`_r_d` — «запомнить устройство»). Ответ 200: `{"redirectUrl": "..."}` — переход по нему открывает кабинет.
Кода подтверждения при входе пользователя по почте не было.

## Список товаров

`POST https://mc.shop.kaspi.kz/bff/offer-view/v2/list?m=<ID продавца>&l=<на странице>&start=<сдвиг>&sortBy=DATE_DESC`
Тело: `{"available": true}` (активные товары). Ответ: `{"total": 54, "data": [...]}`.

Поля товара, которые нам нужны:

| Поле | Что это |
|---|---|
| `sku` | ваш артикул |
| `masterSku` | код карточки на kaspi.kz (по нему — конкуренты и ссылка) |
| `title` / `model`, `brandName` | название, бренд |
| `price`, `cityPrices[{cityId, value}]` | цена (по городам) |
| `availabilities[{storeId, available, stockCount, preOrder, stockSpecified}]` | склад (например `<ID>_PP1`), в наличии, **остаток**, предзаказ |
| `images`, `imagesV2` | фото |
| `masterCategory`, `categoryPathCodes` | категория |
| `minPrice`, `maxPrice`, `rangePrice` | диапазон цен |

## Другие запросы страницы «Управление товарами» (не используем)

- `GET /offers/api/v1/offer/count?m=` — число товаров
- `POST /offers/api/v2/offer/filters/{stock,brands,categories,discounts}?m=` — фильтры
- `GET /offers/api/v1/offer/export/{types,status}?m=&available=ACTIVE` — выгрузка

Изменение цены/остатка в кабинете — отдельные запросы. Мы их **не изучали и не вызываем**:
менять магазин можно только по прямому согласию владельца.
