from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    clerk_user_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'member'"))
    founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("founders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
