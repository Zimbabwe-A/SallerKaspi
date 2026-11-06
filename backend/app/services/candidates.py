"""Подбор ниш: товары-кандидаты, которые пользователь вносит вручную, и их оценка.

Данные с Kaspi здесь не собираются автоматически: пункт 13.1 Пользовательского соглашения
запрещает парсинг. Цены, продавцов и отзывы человек смотрит на сайте сам и вводит в форму.
"""

import math
from datetime import date

from app import db, schemas
from app.services import calculator

# Вклад в итоговую оценку и значения, при которых показатель получает максимум.
MARGIN_WEIGHT, MARGIN_FULL_PCT = 50, 30
DEMAND_WEIGHT, DEMAND_FULL_REVIEWS = 25, 500
COMPETITION_WEIGHT, COMPETITION_ZERO_SELLERS = 25, 15
GOOD_SCORE = 65


def clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def assess(candidate_id: int, updated_at: str, data: schemas.CandidateInput) -> schemas.Candidate:
    economics = calculator.calculate(data)

    margin = MARGIN_WEIGHT * clamp(economics.margin_pct / MARGIN_FULL_PCT)
    demand = DEMAND_WEIGHT * clamp(math.log10(data.reviews + 1) / math.log10(DEMAND_FULL_REVIEWS + 1))
    competition = COMPETITION_WEIGHT * clamp(1 - (data.sellers - 1) / (COMPETITION_ZERO_SELLERS - 1))
    score = round(margin + demand + competition)

    profit_at_min = None
    warnings: list[str] = []
    if data.min_price is not None:
        at_min = calculator.calculate(data.model_copy(update={"price": data.min_price}))
        profit_at_min = at_min.profit
        if data.price > data.min_price:
            gap = f"{(data.price / data.min_price - 1) * 100:.1f}".removesuffix(".0").replace(".", ",")
            warnings.append(f"Ваша цена выше минимальной на {gap}%")
        if at_min.profit <= 0:
            warnings.append("При минимальной цене рынка товар убыточен")
    if data.reviews == 0:
        warnings.append("Нет отзывов: спрос не подтверждён")

    if economics.profit <= 0:
        verdict = "reject"
    elif score >= GOOD_SCORE and economics.margin_pct >= data.target_margin_pct and (profit_at_min or 1) > 0:
        verdict = "good"
    else:
        verdict = "check"

    return schemas.Candidate(
        **data.model_dump(),
        id=candidate_id,
        updated_at=updated_at,
        economics=economics,
        score=score,
        score_parts=schemas.ScoreParts(margin=round(margin), demand=round(demand), competition=round(competition)),
        verdict=verdict,
        profit_at_min_price=profit_at_min,
        warnings=warnings,
    )


def from_row(row) -> schemas.Candidate:
    return assess(row["id"], row["updated_at"], schemas.CandidateInput.model_validate_json(row["data"]))


def list_all() -> list[schemas.Candidate]:
    with db.connect() as connection:
        rows = connection.execute("SELECT * FROM candidates").fetchall()
    return sorted((from_row(r) for r in rows), key=lambda c: (-c.score, c.id))


def create(data: schemas.CandidateInput) -> schemas.Candidate:
    today = date.today().isoformat()
    with db.connect() as connection:
        cursor = connection.execute(
            "INSERT INTO candidates (data, updated_at) VALUES (?, ?)", (data.model_dump_json(), today)
        )
        return assess(cursor.lastrowid, today, data)


def update(candidate_id: int, data: schemas.CandidateInput) -> schemas.Candidate | None:
    today = date.today().isoformat()
    with db.connect() as connection:
        cursor = connection.execute(
            "UPDATE candidates SET data = ?, updated_at = ? WHERE id = ?",
            (data.model_dump_json(), today, candidate_id),
        )
    return assess(candidate_id, today, data) if cursor.rowcount else None


def delete(candidate_id: int) -> bool:
    with db.connect() as connection:
        return connection.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,)).rowcount > 0
