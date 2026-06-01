"""Telemetry ingest — the single, idempotent write path.

Both the Kafka consumer (primary) and the HTTP debug endpoint funnel through
`persist_reading`, so there is exactly one place that decides how a reading is
written. Idempotency = optimistic existence check on `event_id` + the UNIQUE
constraint as the integrity backstop, which also closes the concurrent-consumer
race (two workers handling the same at-least-once delivery). See docs/adr/0003.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Telemetry
from .schemas import TelemetryEvent


@dataclass(frozen=True)
class Reading:
    asset_id: int
    metric: str
    value: float
    recorded_at: datetime
    event_id: str


def reading_from_event(event: TelemetryEvent) -> Reading:
    """Normalise an inbound event, filling server-side defaults."""
    return Reading(
        asset_id=event.asset_id,
        metric=event.metric,
        value=event.value,
        recorded_at=event.recorded_at or datetime.now(timezone.utc),
        event_id=event.event_id or str(uuid4()),
    )


async def persist_reading(session: AsyncSession, reading: Reading) -> bool:
    """Insert a reading idempotently. Returns True if inserted, False if it was
    a duplicate (same event_id already stored)."""
    existing = await session.scalar(
        select(Telemetry.id).where(Telemetry.event_id == reading.event_id)
    )
    if existing is not None:
        return False

    session.add(
        Telemetry(
            asset_id=reading.asset_id,
            metric=reading.metric,
            value=reading.value,
            recorded_at=reading.recorded_at,
            event_id=reading.event_id,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # Lost the race against a concurrent consumer; the row exists now.
        await session.rollback()
        return False
    return True
