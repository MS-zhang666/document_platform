from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database import Base


class Document(Base):
    """
    文档表。
    """

    __tablename__ = "documents"

    # ========================================================
    # Primary Key
    # ========================================================

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    result_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        index=True,
    )

    last_job_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    char_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
