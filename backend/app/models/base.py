from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all FieldShift `public` PostgreSQL ORM models."""

    metadata = MetaData()
