"""API contract + lifecycle integration tests (httpx against the FastAPI app)."""

import pytest


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
