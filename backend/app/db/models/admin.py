from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Admin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-specific extension row. Identity (email, full_name) lives on the User."""

    __tablename__ = "admins"
    __table_args__ = (UniqueConstraint("user_id", name="uq_admins_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="admin")  # type: ignore[name-defined]  # noqa: F821
