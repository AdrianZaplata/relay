"""Pydantic v2 schemas — the API/event contract, separate from the ORM models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .domain import AssetStatus


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=60)


class TransitionRequest(BaseModel):
    to_status: AssetStatus
    reason: str | None = Field(default=None, max_length=280)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    status: AssetStatus
    created_at: datetime
    updated_at: datetime


class AssetEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    from_status: AssetStatus | None
    to_status: AssetStatus
    reason: str | None
    created_at: datetime


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    metric: str
    value: float
    recorded_at: datetime


class TelemetryEvent(BaseModel):
    """The telemetry event contract (the Kafka payload).

    `schema_version` is a forward-compatibility hook: consumers can branch on it
    as the payload evolves, the JSON stand-in for a schema registry. See adr/0003.
    """

    schema_version: int = 1
    asset_id: int
    metric: str
    value: float
    recorded_at: datetime | None = None
    event_id: str | None = None


class TelemetryIngestBody(BaseModel):
    """HTTP debug-ingest body. `asset_id` comes from the URL path, not the body."""

    metric: str
    value: float
    recorded_at: datetime | None = None
    event_id: str | None = None
