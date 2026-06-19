import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    reverse = "reverse"
    delete = "delete"


class AuditLog(UUIDPKMixin, Base):
    """Append-only audit trail (no soft delete)."""

    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action"), nullable=False
    )
    diff_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
