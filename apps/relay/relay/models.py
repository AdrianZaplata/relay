"""SQLAlchemy 2.0 models — the operational (hot) data store.

Design notes (see docs/adr/0002, 0004):
- `status` is a VARCHAR validated in the domain layer, not a native DB ENUM:
  adding a lifecycle state shouldn't require an ALTER TYPE migration.
- `asset_events` is an append-only audit log of every lifecycle transition —
  the "what happened and why" the operator and analytics layer both need.
- `telemetry.event_id` carries a UNIQUE constraint: it's the idempotency key
  that makes at-least-once Kafka delivery safe to replay.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssetEvent(Base):
    """Append-only lifecycle transition log."""

    __tablename__ = "asset_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Telemetry(Base):
    """A single metric reading from an asset.

    Narrow/long shape: one row per (metric, value, time). See docs/adr/0002 for
    why this over a wide row, and how it would partition by time at scale.
    """

    __tablename__ = "telemetry"
    __table_args__ = (
        # Serves the "recent readings for this asset" dashboard query.
        Index("ix_telemetry_asset_recorded", "asset_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Idempotency key: producer-assigned, unique. Makes replay safe.
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
