"""Runtime configuration, read from RELAY_* environment variables.

Centralised settings keep the api and ingestor services configured identically
(they are the same codebase deployed twice), and make secrets injectable at
runtime — the same pattern the platform uses with ExternalSecret Operator.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELAY_", env_file=".env", extra="ignore")

    # Async SQLAlchemy URL. asyncpg in prod; aiosqlite in tests.
    database_url: str = "postgresql+asyncpg://relay:relay@localhost:5432/relay"

    # Kafka / Redpanda
    kafka_bootstrap_servers: str = "localhost:19092"
    telemetry_topic: str = "telemetry"
    consumer_group: str = "relay-ingestor"

    log_level: str = "INFO"


settings = Settings()
