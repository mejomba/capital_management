import uuid
from datetime import datetime

from pydantic import EmailStr

from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    created_at: datetime
