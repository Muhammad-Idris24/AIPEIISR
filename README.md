# AIPEIISR MVP

Human-led, AI-augmented election-information monitoring and fact-checking MVP. Development mode uses safe deterministic mock providers and no live collection source.

Run API: `cd backend; python -m uvicorn app.main:app --reload`.

Run tests: `cd backend; python -m pytest`.

## Auth0 local configuration

Copy `.env.example` to a local `.env` file that is never committed. For the
AIPEIISR Auth0 tenant, set `AUTH0_DOMAIN` to the domain only (no `https://`),
set `AUTH0_AUDIENCE` to the Auth0 API identifier, and set
`AUTH0_ROLES_CLAIM` to the namespaced claim created by the Post-Login Action.
Set `X_ROLE_ENABLED=false` when testing Auth0 so a browser cannot impersonate
an internal role through the development `x-role` header. The API validates
Auth0 RS256 access tokens against the issuer, audience, expiry and public
JWKS signing keys. No Auth0 client secret belongs in this repository.

Read BUILD_STATE.md and AGENT_HANDOFF.md before continuing work. Production requires PostgreSQL, Redis, approved sources, provider terms/credentials and governance decisions in DECISIONS.md.
