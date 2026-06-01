"""Seed demo data: a small fleet of assets in interesting lifecycle states,
plus a little starter telemetry so the dashboard is never empty.

Idempotent: does nothing if assets already exist. Run via `make seed`.
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from .db import SessionLocal, init_models
from .domain import AssetStatus
from .ingest import Reading, persist_reading
from .log import configure_logging
from .models import Asset, AssetEvent

log = logging.getLogger("relay.seed")

# (name, type, [lifecycle path starting from provisioned])
FLEET = [
    ("Charger CP-101", "charge_point", [AssetStatus.ACTIVE]),
    ("Charger CP-102", "charge_point", [AssetStatus.ACTIVE]),
    ("Charger CP-103", "charge_point", [AssetStatus.ACTIVE, AssetStatus.MAINTENANCE]),
    ("Gateway GW-7", "gateway", [AssetStatus.ACTIVE]),
    ("Sensor SN-22", "sensor", []),  # stays provisioned
    ("Charger CP-090", "charge_point", [AssetStatus.ACTIVE, AssetStatus.RETIRED]),
]


async def _seed() -> None:
    await init_models()
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Asset))
        if existing:
            log.info("seed skipped: %d assets already present", existing)
            return

        now = datetime.now(timezone.utc)
        for name, type_, path in FLEET:
            asset = Asset(name=name, type=type_, status=AssetStatus.PROVISIONED)
            session.add(asset)
            await session.flush()  # assign id

            status = AssetStatus.PROVISIONED
            for nxt in path:
                session.add(
                    AssetEvent(
                        asset_id=asset.id,
                        from_status=status,
                        to_status=nxt,
                        reason="seed",
                    )
                )
                status = nxt
            asset.status = status

            # Starter telemetry for active assets so charts render immediately.
            if status == AssetStatus.ACTIVE:
                for i in range(30):
                    ts = now - timedelta(minutes=(30 - i))
                    battery = 80 + 10 * math.sin(i / 5)
                    await persist_reading(
                        session,
                        Reading(
                            asset_id=asset.id,
                            metric="battery",
                            value=round(battery, 2),
                            recorded_at=ts,
                            event_id=str(uuid4()),
                        ),
                    )
        await session.commit()
        log.info("seeded %d assets", len(FLEET))


def main() -> None:
    configure_logging()
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
