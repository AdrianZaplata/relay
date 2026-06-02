"""Relay REST API (FastAPI).

Read + command surface for the operator dashboard. Telemetry's *primary* ingest
path is the Kafka consumer (relay.ingestor); the POST telemetry endpoint here is
a documented debug/seed convenience that reuses the same idempotent writer.
"""

import logging
import math
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import schemas
from .config import settings
from .db import get_session, init_models
from .domain import AssetStatus, IllegalTransition, assert_transition
from .ingest import persist_reading, reading_from_event
from .log import configure_logging
from .models import Asset, AssetEvent, Telemetry

log = logging.getLogger("relay.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    await init_models()
    log.info("relay api started")
    yield


app = FastAPI(title="Relay API", version="0.1.0", lifespan=lifespan)

# Open CORS for the demo so the dashboard on :5173 can call the API on :8000.
# Production would pin the operator app origin(s). See docs/adr/0005.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- health / readiness (K8s probes point here) -----------------------------
@app.get("/healthz", tags=["ops"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


# --- assets ------------------------------------------------------------------
@app.get("/assets", response_model=list[schemas.AssetOut], tags=["assets"])
async def list_assets(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Asset).order_by(Asset.id))
    return result.scalars().all()


@app.post(
    "/assets", response_model=schemas.AssetOut, status_code=201, tags=["assets"]
)
async def create_asset(
    body: schemas.AssetCreate, session: AsyncSession = Depends(get_session)
):
    asset = Asset(name=body.name, type=body.type, status=AssetStatus.PROVISIONED)
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


@app.get("/assets/{asset_id}", response_model=schemas.AssetOut, tags=["assets"])
async def get_asset(asset_id: int, session: AsyncSession = Depends(get_session)):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@app.post(
    "/assets/{asset_id}/transition",
    response_model=schemas.AssetOut,
    tags=["assets"],
)
async def transition_asset(
    asset_id: int,
    body: schemas.TransitionRequest,
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    try:
        assert_transition(asset.status, body.to_status)
    except IllegalTransition:
        # 409 Conflict: the request is well-formed but conflicts with current state.
        raise HTTPException(
            status_code=409,
            detail=f"illegal transition: {asset.status} -> {body.to_status}",
        )
    session.add(
        AssetEvent(
            asset_id=asset.id,
            from_status=asset.status,
            to_status=body.to_status,
            reason=body.reason,
        )
    )
    asset.status = body.to_status
    await session.commit()
    await session.refresh(asset)
    return asset


@app.get(
    "/assets/{asset_id}/events",
    response_model=list[schemas.AssetEventOut],
    tags=["assets"],
)
async def list_asset_events(
    asset_id: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(AssetEvent)
        .where(AssetEvent.asset_id == asset_id)
        .order_by(AssetEvent.created_at, AssetEvent.id)
    )
    return result.scalars().all()


# --- telemetry ---------------------------------------------------------------
@app.get(
    "/assets/{asset_id}/telemetry",
    response_model=list[schemas.TelemetryOut],
    tags=["telemetry"],
)
async def get_telemetry(
    asset_id: int,
    metric: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Telemetry).where(Telemetry.asset_id == asset_id)
    if metric:
        stmt = stmt.where(Telemetry.metric == metric)
    stmt = stmt.order_by(desc(Telemetry.recorded_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(reversed(rows))  # chronological for charting


@app.post(
    "/assets/{asset_id}/telemetry",
    response_model=schemas.TelemetryOut,
    status_code=201,
    tags=["telemetry"],
)
async def ingest_telemetry_http(
    asset_id: int,
    body: schemas.TelemetryIngestBody,
    session: AsyncSession = Depends(get_session),
):
    """Debug/seed ingest path. Primary ingestion is the Kafka consumer."""
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    event = schemas.TelemetryEvent(asset_id=asset_id, **body.model_dump())
    reading = reading_from_event(event)
    await persist_reading(session, reading)
    row = await session.scalar(
        select(Telemetry).where(Telemetry.event_id == reading.event_id)
    )
    return row


# --- fleet map ---------------------------------------------------------------
# A bike that has gone silent for longer than this drops off the live map.
# Bounds the position query to recent telemetry so it scales with fleet size,
# not total table history (the table is append-only and unbounded).
POSITION_MAX_AGE = timedelta(hours=1)


@app.get(
    "/fleet/positions",
    response_model=list[schemas.FleetPosition],
    tags=["fleet"],
)
async def fleet_positions(session: AsyncSession = Depends(get_session)):
    """Latest GPS position (+ battery/speed) per reporting asset, for the map.

    Takes the most recent reading per `(asset_id, metric)` for the position
    metrics via a portable join-on-MAX (a subquery of grouped `max(recorded_at)`
    joined back to the table on equality) — works on Postgres *and* the SQLite
    test DB, avoiding the Postgres-only `DISTINCT ON`. Only assets reporting
    both lat and lng are placeable, so those are the ones we return.

    Bounded to telemetry within `POSITION_MAX_AGE` so the scan stays proportional
    to recent traffic rather than all history.
    """
    metrics = ("lat", "lng", "battery", "speed")
    cutoff = datetime.now(timezone.utc) - POSITION_MAX_AGE
    latest = (
        select(
            Telemetry.asset_id.label("asset_id"),
            Telemetry.metric.label("metric"),
            func.max(Telemetry.recorded_at).label("recorded_at"),
        )
        .where(Telemetry.metric.in_(metrics), Telemetry.recorded_at >= cutoff)
        .group_by(Telemetry.asset_id, Telemetry.metric)
        .subquery()
    )
    stmt = select(Telemetry).join(
        latest,
        and_(
            Telemetry.asset_id == latest.c.asset_id,
            Telemetry.metric == latest.c.metric,
            Telemetry.recorded_at == latest.c.recorded_at,
        ),
    )
    rows = (await session.execute(stmt)).scalars().all()

    # Collapse to one row per (asset, metric). On `recorded_at` ties the join
    # yields multiple rows; keep the newest by `id` so "latest wins" is
    # deterministic instead of an arbitrary DB row order.
    by_asset: dict[int, dict[str, Telemetry]] = {}
    for row in rows:
        current = by_asset.setdefault(row.asset_id, {}).get(row.metric)
        if current is None or row.id > current.id:
            by_asset[row.asset_id][row.metric] = row
    if not by_asset:
        return []

    assets = (
        await session.execute(select(Asset).where(Asset.id.in_(by_asset.keys())))
    ).scalars().all()
    asset_by_id = {a.id: a for a in assets}

    positions: list[schemas.FleetPosition] = []
    for asset_id, metric_map in by_asset.items():
        asset = asset_by_id.get(asset_id)
        # Need both coordinates to place a marker; skip half-reported assets.
        if asset is None or "lat" not in metric_map or "lng" not in metric_map:
            continue
        lat, lng = metric_map["lat"].value, metric_map["lng"].value
        # Guard non-finite coords (a Float column accepts NaN/Inf): they break
        # JSON and place a marker at undefined coordinates on the client.
        if not (math.isfinite(lat) and math.isfinite(lng)):
            continue
        positions.append(
            schemas.FleetPosition(
                asset_id=asset_id,
                name=asset.name,
                type=asset.type,
                status=asset.status,
                lat=lat,
                lng=lng,
                battery=metric_map["battery"].value if "battery" in metric_map else None,
                speed=metric_map["speed"].value if "speed" in metric_map else None,
                recorded_at=max(
                    metric_map["lat"].recorded_at, metric_map["lng"].recorded_at
                ),
            )
        )
    positions.sort(key=lambda p: p.asset_id)
    return positions
