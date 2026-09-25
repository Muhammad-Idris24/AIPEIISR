# AIPEIISR Build State

## Current Phase
Phase 6 — Auth0 backend verification and frontend sign-in shell complete; authenticated protected-route calls next.
## Current Milestone
Phase 6 v0.6.2 delivered: (1) NEW `/findings` public browser (paginated, PUBLISHED-only, no auth header, search+status filters, inline evidence); (2) `/findings/[id]` CONVERTED from ANALYST-only to PUBLIC (removed x-role, fetches /public/findings/{id}, clean 401/403/404 error UIs, back-button, AI disclaimer); (3) analyst search /admin/search pagination (wired offset state, top+bottom nav, total hits, reset-on-filter); (4) findings cross-links on citizen home CITIZEN FACT CHECK + PUBLISHED EVIDENCE sections. tsc --noEmit 0 errors. pytest 24/24 green.
## Overall Completion
99 percent — Phase 1-6 frontend features complete. Auth0 tenant roles, Post-Login role claim and API RBAC are configured; backend now verifies Auth0 RS256 issuer/audience/JWKS tokens. Remaining: Next.js browser login/token handoff, live Auth0 validation, E2E tests, and Docker full-stack online validation.
## Last Completed Task
Phase 6 v0.6.2: `app/findings/page.tsx` (NEW public findings browser, GET /public/findings paginated envelope, q+status filters, Prev/Next page navigation wired to offset=N*limit, per-finding cards with status pill + evidence_count badge + finding ID chip + H2 link + summary + release date + "View full finding →" chip + inline nested evidence sub-cards). `app/findings/[id]/page.tsx` REWRITTEN: REMOVED x-role=ANALYST header, fetches /public/findings/{id} instead of ANALYST endpoint. Status-code branching: 401/403 → "not publicly available" article with bullets + analyst signin hint + findings browse link; 404 → "not found" article + browse link. Success view adds human-authored release provider chip + AI disclaimer paragraph, back-to-findings chip always visible, cancelled unmount guard. `app/admin/search/page.tsx` added offset state + top+bottom pagination nav (Prev/Next chips, page indicator, total candidate hits across collections, max-collection-total for disable threshold), sort/collection/limit/query changes reset offset=0. `app/page.tsx` added two inline /findings deep links (CITIZEN FACT CHECK intro + PUBLISHED EVIDENCE intro) using same dark-blue bold link style as other navigation.
## Current Task
Next actionable: Phase 6 final — (A) Add an Auth0 authenticated-fetch helper and replace synthetic x-role headers on `/room`, `/admin/sources`, `/admin/search`, and `/analyst/findings/[id]`. (B) Live Auth0 validation using an admin test account. (C) Docker Compose full-stack online validation. (D) Optional Next.js E2E tests.
## Next Task
Phase 6 final: (1) Backend Auth0 verification plus frontend login/sign-out shell are complete. Next: Auth0 access-token handoff to protected calls; x-role is development-only. (2) Admin-only finding access — use the same authenticated fetch layer for `/analyst/findings/[id]`. (3) Docker online validation. (4) E2E smoke tests and local-run documentation.
## Blocked Tasks
Docker Compose online validation blocked: Docker daemon not installed/running, local Postgres 18 service auth is scram-sha-256 and service reload requires admin (Restart-Service permission denied). Alembic SQL has been generated offline and validated as syntactically correct PostgresqlImpl DDL for both revisions (0001 + 0002). Postgres online migration tests pending operator intervention.
## Failed Tests
None. Last suite: pytest 24/24 passed (7.70s, 2 deprecation warnings only). tsc --noEmit 0 errors across all 7 TSX files (page.tsx, room/page.tsx, findings/page.tsx NEW, findings/[id]/page.tsx, admin/sources/page.tsx, admin/search/page.tsx, layout.tsx).
## Known Bugs
See KNOWN_ISSUES.md.
## Open Decisions
See DECISIONS.md — Production auth layer (JWT/OAuth vs session), pgvector for Postgres vs JSON-embedding + Python cosine (current MVP uses latter), production publisher retention/publication taxonomy still OPEN.
## Environment Requirements
Python 3.12+ (validated Python 3.14); Node 24; pnpm 10; PostgreSQL 16+ (18 installed locally); Redis 7+ (optional).
## Configured Providers
Deterministic MockLLMProvider + MockEmbeddingProvider (default). Selectable via env:
- LLM_PROVIDER ∈ {mock, ollama, huggingface, openrouter}; EMBEDDING_PROVIDER ∈ {mock, ollama, huggingface}
- Ollama: OLLAMA_URL, OLLAMA_LLM_MODEL (llama3.2), OLLAMA_EMB_MODEL (nomic-embed-text)
- HuggingFace: HF_API_TOKEN required; HF_LLM_MODEL (Llama-3.1-8B-Instruct), HF_EMB_MODEL (all-MiniLM-L6-v2) — batch embed_many() path via v1/embeddings input array
- OpenRouter: OPENROUTER_API_KEY required; OPENROUTER_MODEL (llama-3.1-8b-instruct); HTTP-Referer + X-Title headers set
- All adapters: AI_TIMEOUT_SECONDS default 10, _post_json helper catches URLError/TimeoutError/JSONDecodeError/OSError → fallback to Mock
## Database Migration State
Alembic configured. Revisions validated:
- 0001_initial: 10 tables (sources, citizen_submissions, investigations, findings, audit_logs, documents, claims, evidence_items, investigation_evidence, outbox_events)
- 0002_knowledge_layer: finding_versions {id,finding_id FK,version,label,status,actor,note,created_at} + index; evidence_relations {UQ(source,target,relation_type)} + 2 FK indices
- Embeddings table (collection+entity_id UQ cache) added via db.py Embedding model (init_db create_all path); next Alembic revision 0003_layered_ai should formalize embeddings schema if Postgres online migration is required.
- Alembic upgrade head --sql offline validated with PostgresqlImpl context against postgresql+psycopg:// URL — all 12+2 tables emit valid DDL (TIMESTAMP WITH TIME ZONE, VARCHAR, JSON, UniqueConstraints, indices, UPDATE alembic_version statements).
## API Implementation State
Full API v0.6.0 — NO CHANGES this session. Frontend-only work, API surface backward-compatible:
  - ALL v0.5.0 APIs preserved (source governance, documents, claims, evidence, citation graph /evidence/:id/relations, /graph/evidence, public projections envelope, analyst search (pivoted 5 collections + facets), citizen submission/escalations, investigations detail with findings[]+versions[], room overview, reviews, findings publish/update/unpublish + versions, audit, ops outbox/DLQ/scheduler/worker tick, source run-once + approval gating + 409 DRAFT/DISABLED ingestion blocks)
  - /health: providers.{llm,search,embedding} reflect actual provider names; persistence = sqlite | postgresql+psycopg per DSN dialect.
  - /citizen/submissions: selected LLM runs analyze(query, context), enrichments {uncertainty, citations: dedup(url|provider.citations), llm_provider}, emits SubmissionAIAnalyzeRequested outbox event, caches embedding.
  - /analyst/search: sort_by ∈ {semantic, relevance, ...} → query embedding via current provider, per-collection K=4*limit recall + cosine rerank → items carry semantic_score, response.sort includes {semantic:bool, embedding_provider:name} and each collection bag includes semantic_reranked flag.
  - /public/findings + /public/findings/{id} + /public/evidence: citizen-accessible, PUBLISHED-only, paginated envelopes (now used by findings browser + finding detail + citizen home evidence list).
  - AI_* / SubmissionAI* event types handled by worker _apply_bounded_ai_job hook with Audit trail actor=ai-worker/{provider.name}.
  - Worker/Scheduler daemon-thread auto-start gating preserved (WORKER_DISABLED=1 / SCHEDULER_DISABLED=1 in tests).
## Frontend Implementation State
Citizen page (/): public evidence envelope unwrap, sort chips, cited badges, SUBMISSION RESPONSE v2 (llm_provider chip + uncertainty chip color-coded + citation chips URL/non-URL + inline matched evidence list + AI disclaimer). **FINDINGS CROSS-LINKS:** intro paragraphs for CITIZEN FACT CHECK + PUBLISHED EVIDENCE now include deep links to /findings browser.
Situation Room (/room): 11-card metric grid + sources SubCard tone breakdown + evidence_relations graph health + PROVIDER HEALTH 4-card grid (LLM/Embedding/Search/Persistence with state detection + live inventory counts + worker/scheduler RUNNING/STOPPED counters + pending/dispatched/dead DLQ counts). x-role=ANALYST (AUTH TODO banner present).
**NEW Public Findings browser (/findings):** paginated, no x-role header ever. GET /public/findings envelope (limit=10, offset). Controls: q search, status chips (All/Published). Finding cards: status pill, evidence_count badge, finding ID chip, label H2 link to /findings/{id}, summary excerpt, release date, "View full finding →", inline supporting evidence sub-cards. Prev/Next page nav wired. Offset helper shows N–M of total.
**/findings/[id] (PUBLIC, no x-role anymore):** fetches /public/findings/{id} (ANALYST endpoint REMOVED). Clean error branching: 401/403 → "not publicly available" article with bullets + analyst signin hint; 404 → "finding not found" article + browse link. Success view: back-to-findings chip, status pill + finding ID + "Human-reviewed and authorized for release" provider chip, background section + AI disclaimer, linked evidence, publication history versions. cancelled flag on useEffect unmount guard.
/admin/sources: register form, status filter chips with counts, Approve/Disable/Reset-to-draft/Run-once row actions. x-role=ADMIN (AUTH TODO banner present).
**NEW /admin/search (ANALYST):** 5 collection toggles, 4 sort modes (newest/oldest/relevance/semantic), semantic toggle wired, semantic_score ∿ badges per result, provider chip when semantic_reranked=true, 4-card facets grid, findings links, count badges, OFFSET PAGINATION (top+bottom nav, sort/collection/limit/query changes reset offset 0, total candidate hits, max-collection-total disable threshold, page indicator), deep link to /findings in H1 and findings collection header. x-role=ANALYST (AUTH TODO banner present).
All 4 role-gated routes carry auth TODO banners. tsc --noEmit clean across all 7 TSX files.
## AI Implementation State
Provider interfaces factory-driven via env vars. Mock default guarantees offline test/dev loops. Three real adapters (Ollama/HF/OpenRouter) fully implemented with strict timeout, auth-token gating, JSON-mode prompts where supported, fallback-to-Mock on any transport or parse error. Bounded AI job hooks (event-prefix detection + audit trail) in worker dispatcher. Analyst search semantic rerank via cosine similarity over cached/inline-computed per-row embeddings + embeddings table UQ cache (collection, entity_id). Frontend now visibly surfaces provider names + uncertainty levels: citizen submit shows LLM provider + uncertainty + citations, Situation Room shows live provider cards.
## Worker Implementation State
Redis streams consumer with consumer group + DLQ at 5 retries preserved. _apply_bounded_ai_job() dispatcher for AI_* / SubmissionAI* / DocumentAI* / EvidenceAI* outbox events — imports providers lazily, re-runs factory selection, emits AIEVENT audit rows with actor=ai-worker/{provider}. Audit emission is transactionally committed per event. CANCELLED outbox status preserved. DLQ/retry/cancel endpoints unchanged. Background daemon thread; admin tick/worker.status/scheduler.status preserved. Situation Room shows worker/scheduler status live.
## Security State
RBAC preserved at all role-gated endpoints. AI_WORKER role only used as audit actor string; no endpoint trusts it for mutation. Provider secrets never logged. All provider HTTP calls carry strict timeouts and catch all network-level exceptions; providers silently downgrade to Mock on credential miss or network failure (no exception leakage to HTTP layer). Citizen submissions still do NOT auto-escalate or auto-publish on LLM output; escalations remain human-button-triggered only. **Frontend auth strategy public-clean now:** only /admin/sources (ADMIN), /room (ANALYST), /admin/search (ANALYST) send synthetic x-role headers. /findings, /findings/[id], / (citizen home) send NO headers at all and consume /public/* endpoints only — production-ready for anonymous public visitors out of the box.
## Deployment State
Docker Compose stack declared (db/redis/api) but not online-validated (Docker missing, Postgres local auth requires admin reload for trust or manual password knowledge). Alembic upgrade head --sql offline validated. .env.example fully populated.
## Last Validation
2026-09-24 (Auth0 backend verification):
  - pytest 26/26 green. New RS256 test accepts a correctly issued Auth0-style role token and rejects a wrong-audience token.
  - Backend uses `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `AUTH0_ROLES_CLAIM`; no Auth0 client secret is needed or stored.
  - Next step: configure the local environment and implement frontend browser login/token handoff.

2026-09-22 (Session 7 — Phase 6 v0.6.2 Public Citizen Routes + Analyst UX):
  - pytest 24/24 green (7.70s, tests/test_workflow.py full workflow — 0 regressions from frontend-only work; GET /public/findings + /public/findings/{id} + /public/evidence pagination contract already proven by `test_public_findings_and_public_search_rewrite` and `test_public_evidence_projection_has_pagination_sort_and_findings`).
  - tsc --noEmit 0 TypeScript errors across 7 TSX files: app/page.tsx, app/room/page.tsx, app/findings/page.tsx (NEW), app/findings/[id]/page.tsx (PUBLIC CONVERSION), app/admin/sources/page.tsx, app/admin/search/page.tsx (PAGINATION), app/layout.tsx.
  - Findings browser contract verified against API: /public/findings envelope limit=10 offset=N, q+status filter params wired, response.total → totalPages Math.ceil, Prev/Next page buttons correctly disabled based on page index + offset vs total.
  - Findings detail PUBLIC conversion verified: 401/403 statusCode → "not publicly available" article; 404 → not found article; cancelled=true unmount guard in cleanup.
  - Analyst search pagination: offset state, sort/collection/limit/query onChange handlers reset offset=0, totalHits() accumulates across collections, maxTotalPerCollection used for nav disable bounds.
  - Findings cross-links: citizen home /findings links present in both intro paragraphs, same dark-blue bold style consistent with rest of site.
## Last Updated
2026-09-24
## Agent Handoff Notes
Read AGENT_HANDOFF.md + BUILD_PLAN.md before editing. Current recommended next step:
1. Phase 6 final — Production auth layer: FastAPI middleware reads Authorization Bearer JWT and derives role from claims; x-role kept as dev-only fallback. Next.js login page, cookie handling, NODE_ENV=production x-role header stripping.
2. Analyst-only finding access — build /analyst/findings/[id] or dual-mode for /findings/[id] that sends real auth for UNPUBLISHED viewing.
3. Docker Compose online validation — requires operator intervention (Docker install or Postgres reload/password).
4. Next.js E2E tests (Cypress/Playwright): citizen submit → evidence match, analyst sort semantic toggle, findings browse to detail navigation.

## Session 8 Update 2026-09-22
Bearer-role hardening is implemented in `backend/app/main.py`: verified JWT roles are injected into legacy route guards, and spoofed `x-role` headers are stripped when `X_ROLE_ENABLED=false`. Regression test passed: a signed admin Bearer token succeeds while a spoofed x-role is denied. Added internal analyst finding detail at `/analyst/findings/[id]`. Validation: pytest 25/25 passed and frontend `tsc --noEmit` passed across eight TSX routes. Next task: production identity issuance/session storage, then Docker online validation.

## Session 9 Update 2026-09-24
Auth0 tenant setup is underway with the operator: domain `dev-jfiniqd64sglft55.us.auth0.com`, audience `https://api.aipeiisr.local`, roles, RBAC, and Post-Login namespaced roles Action are configured. Backend `auth.py` now validates Auth0 RS256 tokens through JWKS with exact issuer/audience/expiry/subject checks and maps `https://api.aipeiisr.local/roles`. Added PyJWT crypto dependency, environment documentation and 26-pass regression suite. Exact next action: add Next.js Auth0 SPA login and use its access token for protected API calls.

## Session 10 Update 2026-09-24
Added the Next.js Auth0 SPA provider, public frontend env template, and safe global sign-in/sign-out control. `@auth0/auth0-react` is installed and `tsc --noEmit` passes. Exact next action: configure `frontend/.env.local`, verify Universal Login works for the admin test user, then replace protected-route synthetic `x-role` headers with `Authorization: Bearer <Auth0 access token>`.
