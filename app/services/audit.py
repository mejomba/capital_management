import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction, AuditLog


def record_audit(
    db: Session,
    *,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: AuditAction,
    diff: dict,
) -> AuditLog:
    """Append an audit entry. Does not commit (caller controls the transaction)."""
    entry = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        diff_json=diff,
    )
    db.add(entry)
    return entry
