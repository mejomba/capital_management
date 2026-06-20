import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, page_params
from app.schemas.common import Page
from app.schemas.goal import GoalCreate, GoalDetailOut, GoalOut, GoalUpdate
from app.services import goals as goal_service

router = APIRouter(tags=["goals"])


@router.get("/goals", response_model=Page[GoalOut])
def list_goals(
    current_user: CurrentUser,
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[GoalOut]:
    items, total = goal_service.list_goals(db, current_user.id, params)
    return Page[GoalOut](
        items=[GoalOut.model_validate(g) for g in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate, current_user: CurrentUser, db: DbSession) -> GoalOut:
    goal = goal_service.create_goal(db, current_user.id, data)
    return GoalOut.model_validate(goal)


@router.get("/goals/{goal_id}", response_model=GoalDetailOut)
def get_goal(goal_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> GoalDetailOut:
    goal = goal_service.get_goal(db, current_user.id, goal_id)
    progress = goal_service.compute_progress(db, current_user.id, goal)
    goal.progress = progress
    return GoalDetailOut.model_validate(goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: uuid.UUID, data: GoalUpdate, current_user: CurrentUser, db: DbSession
) -> GoalOut:
    goal = goal_service.update_goal(db, current_user.id, goal_id, data)
    return GoalOut.model_validate(goal)
