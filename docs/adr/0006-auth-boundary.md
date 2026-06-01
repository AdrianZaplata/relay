# ADR 0006 — Auth boundary (Keycloak / OIDC)

**Status:** accepted as design · **not fully implemented in this build** (see [TRADEOFFS](../TRADEOFFS.md))

## Context

The platform serves two audiences with different rights: **operators** (B2B — manage
their fleet) and **riders** (B2C — their own bike/rides). The platform standard is
**Keycloak** for identity. Relay needs a defensible answer for "how does auth work",
even where the demo leaves it unimplemented.

## Decision (design)

- **Keycloak is the IdP.** The API is an OAuth2 **resource server**: it validates OIDC
  **access tokens** (JWT, RS256) on protected routes — checks signature against
  Keycloak's JWKS, plus `iss` / `aud` / `exp`, and authorises on `scope`/role claims.
- **Frontend** uses the **Authorization Code flow with PKCE** (public SPA client),
  stores no client secret, sends the bearer token to the API.
- **Multi-tenancy:** a `tenant`/`operator` claim in the token scopes every query to that
  operator's assets (row-level isolation) — one operator never sees another's fleet.
- **Service-to-service** (e.g. ingestor) uses the client-credentials grant.

## Why token validation at the edge

Stateless verification (no IdP round-trip per request), standard OIDC so Keycloak owns
login/MFA/federation, and a clean separation: the IdP authenticates, the API authorises.

## Consequences / honesty

This build does **not** wire Keycloak — it would be ~1–2h (realm, client, JWT
middleware, SPA login) and is the highest-risk-to-finish item. Documenting the boundary
precisely is more valuable here than a half-working login. A single protected route
would be the minimal proof.

## At production scale

Secrets (client credentials) injected at runtime via **ExternalSecret Operator** backed
by the platform's secret manager — never baked into images or git.
