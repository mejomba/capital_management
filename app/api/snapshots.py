from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.snapshot import RebuildRequest, RebuildResult, SnapshotOut
from app.services import snapshots as snapshot_service

router = APIRouter(tags=["snapshots"])


@router.get("/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[SnapshotOut]:
    rows = snapshot_service.list_snapshots(db, current_user.id, date_from, date_to)
    return [SnapshotOut.model_validate(r) for r in rows]


@router.post(
    "/snapshots/rebuild", response_model=RebuildResult, status_code=status.HTTP_201_CREATED
)
def rebuild_snapshots(
    data: RebuildRequest, current_user: CurrentUser, db: DbSession
) -> RebuildResult:
    created = snapshot_service.backfill(db, current_user.id, data.date_from, data.date_to)
    return RebuildResult(created=created, date_from=data.date_from, date_to=data.date_to)
