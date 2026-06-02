"""API contract + lifecycle integration tests (httpx against the FastAPI app)."""

from datetime import datetime, timedelta, timezone

import pytest

from relay.models import Asset, Telemetry


async def _create(client, name="Charger CP-1", type_="charge_point"):
    r = await client.post("/assets", json={"name": name, "type": type_})
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_create_asset_starts_provisioned(client):
    body = await _create(client)
    assert body["status"] == "provisioned"

    got = await client.get(f"/assets/{body['id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "provisioned"


@pytest.mark.asyncio
async def test_legal_transition_updates_status_and_logs_event(client):
    asset = await _create(client)
    aid = asset["id"]

    r = await client.post(
        f"/assets/{aid}/transition",
        json={"to_status": "active", "reason": "commissioned"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    events = (await client.get(f"/assets/{aid}/events")).json()
    assert len(events) == 1
    assert events[0]["from_status"] == "provisioned"
    assert events[0]["to_status"] == "active"
    assert events[0]["reason"] == "commissioned"


@pytest.mark.asyncio
async def test_illegal_transition_returns_409_and_leaves_state_unchanged(client):
    asset = await _create(client)
    aid = asset["id"]

    # provisioned -> retired is not allowed
    r = await client.post(f"/assets/{aid}/transition", json={"to_status": "retired"})
    assert r.status_code == 409

    # status is unchanged ...
    assert (await client.get(f"/assets/{aid}")).json()["status"] == "provisioned"
    # ... and no spurious audit event was written
    assert (await client.get(f"/assets/{aid}/events")).json() == []


@pytest.mark.asyncio
async def test_telemetry_roundtrip_via_debug_endpoint(client):
    asset = await _create(client)
    aid = asset["id"]
    await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})

    r = await client.post(
        f"/assets/{aid}/telemetry",
        json={"metric": "battery", "value": 91.5, "event_id": "evt-roundtrip"},
    )
    assert r.status_code == 201

    series = (await client.get(f"/assets/{aid}/telemetry?metric=battery")).json()
    assert len(series) == 1
    assert series[0]["value"] == 91.5


@pytest.mark.asyncio
async def test_fleet_positions(client):
    asset = await _create(client, name="Pedelec SPV2-9001", type_="ebike")
    aid = asset["id"]
    await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})

    # No GPS reported yet → the bike isn't placeable, so the map is empty.
    assert (await client.get("/fleet/positions")).json() == []

    # Report position (+ vitals) through the debug ingest path.
    readings = [("lat", 52.52), ("lng", 13.405), ("battery", 88.0), ("speed", 17.5)]
    for metric, value in readings:
        r = await client.post(
            f"/assets/{aid}/telemetry",
            json={"metric": metric, "value": value, "event_id": f"{metric}-1"},
        )
        assert r.status_code == 201

    positions = (await client.get("/fleet/positions")).json()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["asset_id"] == aid
    assert pos["name"] == "Pedelec SPV2-9001"
    assert pos["status"] == "active"
    assert pos["lat"] == 52.52
    assert pos["lng"] == 13.405
    assert pos["battery"] == 88.0
    assert pos["speed"] == 17.5


@pytest.mark.asyncio
async def test_fleet_positions_skips_asset_reporting_only_lat(client):
    asset = await _create(client, name="Pedelec SPV2-9002", type_="ebike")
    aid = asset["id"]
    await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})

    # Only latitude reported — not placeable, so it must not appear on the map.
    r = await client.post(
        f"/assets/{aid}/telemetry",
        json={"metric": "lat", "value": 52.52, "event_id": "lat-only"},
    )
    assert r.status_code == 201

    assert (await client.get("/fleet/positions")).json() == []


@pytest.mark.asyncio
async def test_fleet_positions_null_battery_and_speed_when_unreported(client):
    asset = await _create(client, name="Pedelec SPV2-9003", type_="ebike")
    aid = asset["id"]
    await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})

    for metric, value in [("lat", 52.52), ("lng", 13.405)]:  # no battery/speed
        r = await client.post(
            f"/assets/{aid}/telemetry",
            json={"metric": metric, "value": value, "event_id": f"{metric}-nb"},
        )
        assert r.status_code == 201

    pos = (await client.get("/fleet/positions")).json()[0]
    assert pos["battery"] is None
    assert pos["speed"] is None


@pytest.mark.asyncio
async def test_fleet_positions_drops_non_finite_battery_and_speed(client, session_factory):
    # A Float column accepts non-finite values and nothing rejects them at
    # ingest, so they can reach the DB. Contract: a bad optional vital surfaces as
    # null, and the asset still shows with valid coordinates. (Pydantic already
    # renders non-finite as null; this pins that behavior so it can't silently
    # regress.) Insert directly: a JSON-encoded request body can't carry NaN/Inf.
    # We use Inf for both vitals because SQLite coerces NaN to NULL (Postgres
    # stores it); Inf reproduces the same non-finite path on either backend.
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        asset = Asset(name="Pedelec SPV2-9009", type="ebike", status="active")
        session.add(asset)
        await session.flush()
        aid = asset.id
        session.add_all(
            Telemetry(
                asset_id=aid,
                metric=metric,
                value=value,
                recorded_at=now,
                event_id=f"{metric}-nf",
            )
            for metric, value in [
                ("lat", 52.52),
                ("lng", 13.405),
                ("battery", float("inf")),
                ("speed", float("-inf")),
            ]
        )
        await session.commit()

    resp = await client.get("/fleet/positions")
    assert resp.status_code == 200
    pos = resp.json()[0]
    assert pos["asset_id"] == aid
    assert pos["lat"] == 52.52
    assert pos["lng"] == 13.405
    assert pos["battery"] is None
    assert pos["speed"] is None


@pytest.mark.asyncio
async def test_fleet_positions_includes_non_active_asset(client):
    # A bike that never activated still shows on the map (greyed out client-side);
    # the API does not filter by status.
    asset = await _create(client, name="Pedelec SPV2-9004", type_="ebike")
    aid = asset["id"]
    for metric, value in [("lat", 52.52), ("lng", 13.405)]:
        r = await client.post(
            f"/assets/{aid}/telemetry",
            json={"metric": metric, "value": value, "event_id": f"{metric}-prov"},
        )
        assert r.status_code == 201

    positions = (await client.get("/fleet/positions")).json()
    assert len(positions) == 1
    assert positions[0]["status"] == "provisioned"


@pytest.mark.asyncio
async def test_fleet_positions_multiple_assets_sorted_by_id(client):
    ids = []
    for i in range(2):
        asset = await _create(client, name=f"Pedelec SPV2-905{i}", type_="ebike")
        aid = asset["id"]
        await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})
        for metric, value in [("lat", 52.5 + i), ("lng", 13.4 + i)]:
            await client.post(
                f"/assets/{aid}/telemetry",
                json={"metric": metric, "value": value, "event_id": f"{metric}-{aid}"},
            )
        ids.append(aid)

    positions = (await client.get("/fleet/positions")).json()
    assert [p["asset_id"] for p in positions] == sorted(ids)


@pytest.mark.asyncio
async def test_fleet_positions_latest_reading_wins(client):
    asset = await _create(client, name="Pedelec SPV2-9005", type_="ebike")
    aid = asset["id"]
    await client.post(f"/assets/{aid}/transition", json={"to_status": "active"})

    await client.post(
        f"/assets/{aid}/telemetry",
        json={"metric": "lng", "value": 13.405, "event_id": "lng-lw"},
    )
    # Two latitudes with distinct, recent timestamps — the newer fix must win.
    # Recent so they stay inside the POSITION_MAX_AGE window.
    now = datetime.now(timezone.utc)
    older = (now - timedelta(minutes=5)).isoformat()
    newer = (now - timedelta(minutes=1)).isoformat()
    await client.post(
        f"/assets/{aid}/telemetry",
        json={"metric": "lat", "value": 52.40, "recorded_at": older, "event_id": "lat-old"},
    )
    await client.post(
        f"/assets/{aid}/telemetry",
        json={"metric": "lat", "value": 52.52, "recorded_at": newer, "event_id": "lat-new"},
    )

    pos = (await client.get("/fleet/positions")).json()[0]
    assert pos["lat"] == 52.52
