# ADR 0004 — Asset lifecycle as an explicit, audited state machine

**Status:** accepted

## Context

An asset (a bike, a battery) moves through a lifecycle: `provisioned → active →
maintenance → retired`. Some transitions are legal, most are not (you can't retire a
bike straight from provisioned, you can't un-retire). Every change must be **auditable**
— operators and analytics both need to know *what changed, when, and why*.

## Decision

- A single **transition table** is the source of truth, enforced by a pure,
  dependency-free domain function (`relay/domain.py`):

  ```
  provisioned → {active}
  active      → {maintenance, retired}
  maintenance → {active, retired}
  retired     → {}            (terminal)
  ```

- Every successful transition appends an **`asset_events`** row
  (`from_status`, `to_status`, `reason`, `created_at`) — an append-only audit log.
- An illegal transition returns **409 Conflict** and writes nothing.

## Why enforce in the application, not just the database

- The rule depends on the *current* state — richer than a column `CHECK`.
- The app returns a clear, typed error; a DB constraint violation is opaque to clients.
- It lives in **one pure function** that's trivially unit-tested (no DB, no framework).
- `status` is a `VARCHAR` validated in the domain layer, **not a native DB `ENUM`** —
  adding a lifecycle state shouldn't require an `ALTER TYPE` migration.

## Consequences

- The application must be the only writer of `status` (no raw SQL bypassing the rule).
  Acceptable: all writes go through the service.

## At production scale

The `asset_events` log doubles as an **event-sourcing feed**: "mean time in
maintenance", "how many bikes were retired this quarter" fall straight out of it,
feeding the analytics layer ([0001](0001-hot-cold-data-split.md)).
