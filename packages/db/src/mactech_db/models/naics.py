from datetime import datetime

from sqlalchemy import TIMESTAMP, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class NaicsCode(Base):
    __tablename__ = "naics_codes"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    size_standard: Mapped[str | None] = mapped_column(String, nullable=True)
    mactech_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
