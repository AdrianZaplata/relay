"""The ingest writer must be idempotent: replaying an event (at-least-once Kafka
delivery) must not create duplicate rows."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from relay.domain import AssetStatus
from relay.ingest import Reading, persist_reading
from relay.models import Asset, Telemetry


@pytest.mark.asyncio
async def test_duplicate_event_id_is_ingested_once(session_factory):
    async with session_factory() as session:
        asset = Asset(name="CP-1", type="charge_point", status=AssetStatus.ACTIVE)
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

        reading = Reading(
            asset_id=asset.id,
            metric="battery",
            value=88.0,
            recorded_at=datetime.now(timezone.utc),
            event_id="evt-dup",
        )

        first = await persist_reading(session, reading)
        second = await persist_reading(session, reading)

        assert first is True
        assert second is False

        count = await session.scalar(
            select(func.count()).select_from(Telemetry).where(
                Telemetry.event_id == "evt-dup"
            )
        )
        assert count == 1
