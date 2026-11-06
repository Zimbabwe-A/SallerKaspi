from fastapi import APIRouter, HTTPException, Response

from app import schemas, tariffs
from app.services import calculator, candidates

router = APIRouter(tags=["Подбор ниш"])


@router.get("/tariffs", response_model=schemas.Tariffs, summary="Тарифы Kaspi для калькулятора")
def get_tariffs():
    return schemas.Tariffs(
        commission_presets=tariffs.COMMISSION_PRESETS,
        delivery_types=[{"id": k, "label": v} for k, v in tariffs.DELIVERY_TYPES.items()],
        weight_tiers=[{"id": k, "label": v["label"]} for k, v in tariffs.WEIGHT_TIERS.items()],
        default_tax_pct=tariffs.DEFAULT_TAX_PCT,
        default_target_margin_pct=tariffs.DEFAULT_TARGET_MARGIN_PCT,
        commission_source=tariffs.COMMISSION_SOURCE,
        delivery_source=tariffs.DELIVERY_SOURCE,
        checked_at=tariffs.CHECKED_AT,
    )


@router.post("/calculator", response_model=schemas.Economics, summary="Юнит-экономика одной продажи")
def post_calculator(data: schemas.EconomicsInput):
    return calculator.calculate(data)


@router.get("/candidates", response_model=list[schemas.Candidate], summary="Кандидаты, лучшие сверху")
def get_candidates():
    return candidates.list_all()


@router.post("/candidates", response_model=schemas.Candidate, status_code=201, summary="Добавить кандидата")
def post_candidate(data: schemas.CandidateInput):
    return candidates.create(data)


@router.put("/candidates/{candidate_id}", response_model=schemas.Candidate, summary="Изменить кандидата")
def put_candidate(candidate_id: int, data: schemas.CandidateInput):
    candidate = candidates.update(candidate_id, data)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    return candidate


@router.delete("/candidates/{candidate_id}", status_code=204, summary="Удалить кандидата")
def delete_candidate(candidate_id: int):
    if not candidates.delete(candidate_id):
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    return Response(status_code=204)
