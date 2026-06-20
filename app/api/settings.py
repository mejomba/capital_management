from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.assumptions import AssumptionsOut, AssumptionsUpdate
from app.schemas.inflation import InflationRateCreate, InflationRateOut
from app.services import assumptions as assumptions_service

router = APIRouter(tags=["settings"])


@router.get("/assumptions", response_model=AssumptionsOut)
def get_assumptions(current_user: CurrentUser, db: DbSession) -> AssumptionsOut:
    return AssumptionsOut.model_validate(
        assumptions_service.get_assumptions(db, current_user.id)
    )


@router.put("/assumptions", response_model=AssumptionsOut)
def put_assumptions(
    data: AssumptionsUpdate, current_user: CurrentUser, db: DbSession
) -> AssumptionsOut:
    return AssumptionsOut.model_validate(
        assumptions_service.upsert_assumptions(db, current_user.id, data)
    )


@router.get("/inflation", response_model=list[InflationRateOut])
def list_inflation(current_user: CurrentUser, db: DbSession) -> list[InflationRateOut]:
    rows = assumptions_service.list_inflation(db, current_user.id)
    return [InflationRateOut.model_validate(r) for r in rows]


@router.post("/inflation", response_model=InflationRateOut, status_code=status.HTTP_201_CREATED)
def create_inflation(
    data: InflationRateCreate, current_user: CurrentUser, db: DbSession
) -> InflationRateOut:
    row = assumptions_service.upsert_inflation(db, current_user.id, data)
    return InflationRateOut.model_validate(row)
