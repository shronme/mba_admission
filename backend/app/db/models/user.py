from __future__ import annotations

from sqlalchemy import Enum as SQLEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import UserRole
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Central identity record shared by candidates and admins.
    Role determines which domain table (candidates / admins) holds the extension row.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", native_enum=True),
        nullable=False,
    )

    candidate: Mapped["Candidate | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    admin: Mapped["Admin | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["UserSession"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
    )
