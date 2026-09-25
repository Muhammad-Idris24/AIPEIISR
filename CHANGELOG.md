# Changelog

## 2026-09-24 (Auth0 frontend sign-in shell)
- Added `@auth0/auth0-react` 2.27.0 and a root `AppAuthProvider` configured for the AIPEIISR Auth0 domain, Client ID, audience and local redirect URL.
- Added a minimal global sign-in/sign-out control. It requests API-scoped access tokens; no token is rendered, persisted by application code, or logged.
- Added `frontend/.env.example` for public browser configuration and validated the frontend with `tsc --noEmit` (0 errors).
- Protected-route token handoff is deliberately the next step; existing synthetic `x-role` headers have not been converted yet.

## 2026-09-24 (Auth0 backend verification)
- Added Auth0 RS256 access-token validation using Auth0's JWKS endpoint. Tokens must have the configured issuer, audience, expiry, subject, RS256 algorithm and `https://api.aipeiisr.local/roles` namespaced roles claim.
- Auth0 role arrays resolve least-privilege by default; unsupported or missing roles become `CITIZEN`. When Auth0 is configured, the legacy HS256 development path is not accepted.
- Added `PyJWT[crypto]==2.15.0`, Auth0 environment-variable documentation, Compose pass-through configuration, and a root `.gitignore` that excludes local environment files.
- Added regression coverage for an Auth0-style RS256 access token: a valid admin token can create a source and a token with a wrong audience is denied. Backend suite: 26 passed.

## 2026-09-22 (Session 7 — Phase 6 Public Citizen Routes + Analysts UX v0.6.2)
- **API version unchanged (0.6.0)**. No backend code modified in this session; frontend-only work, endpoints fully backward-compatible.
- **PUBLIC FINDINGS BROWSER (`/findings`)** — New route `app/findings/page.tsx` consuming GET `/public/findings` paginated envelope (limit/offset + status filter + q search params):
  - Public, no x-role header sent ever. Returns only PUBLISHED findings, 401/403 UI for unpublished.
  - Controls: search input (finding label filter, resets to page 0), status chips (All / Published), Prev/Next page navigation wired to `offset=N*limit` pagination.
  - Result cards: status pill + evidence_count badge + finding ID chip, finding label as H2 link to `/findings/{id}`, optional summary excerpt, release date, "View full finding →" chip, inline nested supporting evidence list (evidence excerpt cards, review badges, source links).
  - Helper `offsetHelper` shows `N–M of total` line, page indicator `{page+1}/{totalPages}` in nav bar, Prev disabled on page 0, Next disabled when (page+1)*limit >= total.
- **PUBLIC FINDING DETAIL ROUTE** — Rewrote `app/findings/[id]/page.tsx`:
  - **REMOVED x-role=ANALYST header** — Now fetches `GET /public/findings/{id}` (no auth header), so this route is citizen-safe for public deployment.
  - Clean HTTP error branching by statusCode state: 401/403 → dedicated "not publicly available" article with explanation bullets, analyst-signin hint, and findings browse link. 404 → "finding not found" article with browse link. Generic 5xx/network errors render only error paragraph (not leak internal API shape).
  - "Back to all findings" chip at top of every view (success, 403, 404).
  - Success view adds: green "Human-reviewed and authorized for release" provider chip in meta row, AI tooling disclaimer paragraph in background section, "Referenced citizen submission:" renamed from just "submission_id" to be explicit.
  - `cancelled` flag on useEffect avoids setState-after-unmount race if user clicks away during fetch.
- **ANALYST SEARCH PAGINATION + UX** — Updated `app/admin/search/page.tsx`:
  - New `offset` state variable, wired to POST `/analyst/search` `AnalystSearchIn.offset` field.
  - Sort / collection / limit / query changes ALL reset offset back to 0 so new searches start at page 1.
  - Two pagination bars (top under search controls, bottom after last result card): Prev / Next buttons, page indicator "page N · showing {limit} per page", total candidate hits computed across selected collections, offset indicator showing per-collection window.
  - `totalHits()` sums `bag.total` across selected collections; `maxTotalPerCollection()` determines Next disable threshold (multi-collection pagination uses the largest collection total as the upper bound — good enough MVP for analyst tooling).
  - H1 intro paragraph adds "browse published findings here →" inline deep link to `/findings`.
  - Findings collection header adds a "Browse all findings" chip-on button linking to `/findings`.
  - View finding chip link text changed from "View finding" to "View finding →" for visual consistency with findings browser.
- **FINDINGS CROSS-LINK NAVIGATION** — Updated `app/page.tsx` citizen home:
  - CITIZEN FACT CHECK intro paragraph adds "browse all published findings →" deep link.
  - PUBLISHED EVIDENCE intro paragraph adds "browse published findings by category →" deep link.
  - Both links use the same #173f5f dark-blue + font-weight:600 link style that matches other inline navigation.
- **Validations:**
  - tsc --noEmit 0 errors across all 7 route files (page.tsx, room/page.tsx, findings/[id]/page.tsx, findings/page.tsx (NEW), admin/sources/page.tsx, admin/search/page.tsx, layout.tsx).
  - pytest 24/24 green (7.70s, tests/test_workflow.py full workflow — all backward compatible because frontend-only changes; GET /public/findings, GET /public/findings/{id}, GET /public/evidence pagination already tested in `test_public_findings_and_public_search_rewrite` + `test_public_evidence_projection_has_pagination_sort_and_findings` — API envelopes unchanged).
  - Error branches verified in code: 403/401 findings detail → "not publicly available" friendly error page, 404 → not found link, fetch exceptions → alert paragraph. Pagination disable logic verified: prev disabled when offset=0, next disabled when offset+limit >= max-collection-total.

## 2026-09-22 (Session 6 — Phase 5 Frontend Polish v0.6.1)
- **API version unchanged (0.6.0)**. No backend code modified in this session.
- **ANALYST SEARCH UI** — New route `app/admin/search/page.tsx` at `/admin/search`:
  - Multi-collection query input + collection toggle chips (Investigations / Evidence / Claims / Documents / Findings), top-N limit selector (10/25/50/100).
  - 4-position sort bar (Newest / Oldest / Relevance / Semantic) wired to POST `/analyst/search` `sort_by` field.
  - When `sort=semantic` and API reports `sort.semantic=true`, renders purple `Semantic rerank · {embedding_provider}` chip and per-collection `Semantic reranked` flag.
  - Every result item carries a `∿ 0.XXX` **semantic_score badge** (deep blue, cosine similarity rounded to 3 decimals) with tooltip explaining score, sort mode and provider.
  - Per-collection result cards render status pills, cited badges, finding/evidence/claim/version/investigation count chips, cross-linked evidence/sources, and "View finding" links for findings collections.
  - 4-card Facets subgrid renders investigation statuses, evidence review statuses, claim uncertainty buckets, and source statuses with per-key counts.
- **SITUATION ROOM PROVIDER HEALTH** — Rewrote `app/room/page.tsx` to fetch BOTH `/room/overview` (existing metrics) AND `/health` (new provider/persistence/worker/scheduler data) in parallel:
  - New **AI PROVIDER HEALTH** block with 4-card `health-providers` grid: LLM Analyze, Embedding, Search, Persistence. Each card auto-detects state by name (Mock=grey mock card, live providers + postgres/sqlite=green online, missing=red offline).
  - Live inventory subgrid: Sources in DB / Documents in DB / Claims in DB / Finding versions (all from `/health.inventory`).
  - Worker status row: `RUNNING/STOPPED` chip + Pending/Dispatched/Dead(DLQ) counts.
  - Scheduler status row: `RUNNING/STOPPED` chip + Sources total/Approved counts.
  - Provider state helper parses `ollama/huggingface/hf/openrouter/gpt/gemini/claude` as live, `mock` as mock, default fallback.
  - Added helper text explaining factory env-var selection + Mock fallback + timeout gating.
- **CITIZEN SUBMISSION ENRICHMENTS** — Rewrote `app/page.tsx` submission response rendering:
  - Meta row: status badge + **`LLM · {llm_provider}`** chip (tone-coded by provider name: mock=grey, live=green) + **`Uncertainty · {level}`** chip (high=red, medium=amber, low=green, unknown=grey) with hover tooltips.
  - Enrichments row: Human review status badge + published evidence count badge.
  - **Citations row** (new): renders every entry in `citations[]` array — URLs become clickable `citation-chip external` links (target=_blank), non-URLs become plain `citation-chip` badges. Both carry tooltips explaining provider citations are non-authoritative.
  - Inline Relevant Published Evidence list (new): if `public_evidence[]` has matches, renders a full evidence-card list (review status, cited count, source link, excerpt, findings cross-links) directly in the submission card so the citizen sees matches immediately without scrolling.
  - Footer disclaimer reminding users AI-assisted analysis only, human publishers authorize findings.
- **AUTH LAYER TODO SCAFFOLD** — Added visible `auth-todo` amber banners to all 4 role-gated route pages, directly below the H1:
  - `/room` → x-role=ANALYST + JWT/OAuth/session integration note.
  - `/admin/sources` → x-role=ADMIN + JWT/OAuth/session integration note.
  - `/admin/search` → x-role=ANALYST + JWT/OAuth/session integration note.
  - `/findings/[id]` → x-role=ANALYST + "build public citizen-only variant (no x-role)" note.
  - CSS: `.auth-todo` class added in styles.css — amber background, padded warning banner, 12px bold text, positioned directly under H1 so every dev-visible route shows the TODO.
- **styles.css additions** — 32 new CSS classes covering: `.semantic-badge` (deep blue ∿ score pill), `.provider-chip` variants (llm/emb/search/semantic/mock/online/offline — 8 variants), `.count-badge` (pale generic counter), `.facets-grid` (4-col responsive, collapses 2-col mobile), `.search-input` / `.limit-select` (analyst search controls), `.citation-chip` + `.citation-chip.external` (URL vs non-URL citation badges), `.uncertainty-{high,medium,low,unknown}` (4 tone codes), `.enrichments-row` (dashed separator for meta rows), `.health-providers` (4-col provider grid), `.provider-card` (card with kind/name/status-dot children, 3 tone variants online/offline/mock), `.auth-todo` (amber warning banner), and mobile breakpoints for facets-grid + health-providers.
- **Validations:**
  - tsc --noEmit 0 errors across all 5 route files + 1 layout file (page.tsx, room/page.tsx, findings/[id]/page.tsx, admin/sources/page.tsx, admin/search/page.tsx, layout.tsx).
  - pytest 24/24 green (8.58s, 2 standard deprecation warnings for httpx2 + anyio.BlockingPortal — no new warnings, no regressions). Backend untouched; tests verify analyst/search API contract, /health payload shape (providers dict, worker+scheduler statuses, inventory) are all backward-compatible.

## 2026-09-22 (Session 5 — Phase 4 Provider Interfaces v0.6.0)
- API version bumped 0.5.0 → 0.6.0.
- **providers.py rewrite** — Added `LLMProvider` and `EmbeddingProvider` Protocols. Introduced env-var driven factory functions `get_llm_provider()` / `get_embedding_provider()` with deterministic Mock defaults.
  - **MockLLMProvider / MockEmbeddingProvider** preserved as always-available deterministic fallbacks (default for LLM_PROVIDER=mock, EMBEDDING_PROVIDER=mock).
  - **OllamaLLMProvider** — hits `OLLAMA_URL/api/generate` with JSON-mode prompt ("Respond ONLY as valid JSON {claim,entities,uncertainty,citations}"), temperature 0, parses `response` JSON string into `Analysis`. Falls back to MockAnalysis on any failure.
  - **OllamaEmbeddingProvider** — hits `OLLAMA_URL/api/embeddings`, returns raw `embedding` list. Falls back to MockEmbedding on failure.
  - **HuggingFaceLLMProvider** — requires `HF_API_TOKEN`. Hits `router.huggingface.co/hf-inference/models/{model}/v1/chat/completions` with system+user messages, JSON object response format requested, 300 max tokens, temperature 0. Parses `choices[0].message.content` JSON. Falls back to Mock when token empty or request fails.
  - **HuggingFaceEmbeddingProvider** — requires `HF_API_TOKEN`. `embed()` single-call path, plus optimized `embed_many()` batch path via `input:[]` array with per-row `index` keying so embeddings align even if HF shuffles. Falls back to Mock embedding for empty-token or failed rows.
  - **OpenRouterLLMProvider** — requires `OPENROUTER_API_KEY`. Hits `openrouter.ai/api/v1/chat/completions` with `HTTP-Referer: aipieisr.local` and `X-Title: AIPEIISR` attribution headers required by ToS. Same strict JSON parser + Mock fallback.
  - Shared `_post_json(url, payload, headers)` helper uses stdlib `urllib.request` (no httpx/requests dependency added) with `AI_TIMEOUT_SECONDS` (default 10). Catches `URLError / TimeoutError / JSONDecodeError / OSError` → returns `None` → Mock fallback chain. No secrets logged.
  - Factory `get_llm_provider(kind=None)` selects by env-var `LLM_PROVIDER` (mock|ollama|huggingface|openrouter). Invalid/unset kind → MockLLMProvider. Factory exceptions wrapped so import-time issues never prevent startup. `get_embedding_provider(kind=None)` for EMBEDDING_PROVIDER (mock|ollama|huggingface).
- **db.py** — Added `cosine_similarity(a,b)` math helper for pure-Python MVP embedding comparison. Exported `IS_SQLITE` flag + `URL as DB_URL` so callers can report dialect. Added new ORM model `Embedding` with columns `{id PK, collection index, entity_id index, provider, dim, vector JSON, updated_at onupdate=now}` + UniqueConstraint(`collection`,`entity_id`, name='uq_embeddings_collection_entity'). This acts as a cache so repeated calls to embed the same row don't re-hit the provider. `init_db()` creates this via `Base.metadata.create_all`.
- **main.py** — Replaced direct `MockLLMProvider()` / `MockEmbeddingProvider()` singletons with `llm=get_llm_provider()` / `emb=get_embedding_provider()`. Added two internal helpers:
  - `_embed_text(collection, entity_id, text)` — upserts into embeddings cache, returns vector (or `None` on provider failure). Reads cache first, skips recompute if existing `provider+dim` matches current.
  - `_semantic_rerank(collection, query_vec, rows, text_for_row, limit)` — for each row, reuses cached embedding or computes inline, scores via cosine_similarity, sorts DESC, limits results, attaches `semantic_score` field per item. Works on both ORM instances + plain dicts.
  - Updated `/health` — providers dict now carries actual `llm.name` and `emb.name`; persistence field reports dialect (`sqlite` or the DSN scheme, e.g. `postgresql+psycopg`) instead of hardcoded string.
  - Updated `POST /citizen/submissions` — no longer hardcodes analysis="AI-assisted…". Now runs `llm.analyze(query, context)`, composes a rich human-readable `analysis` string (claim summary, entities list, provider citations warning, published-or-no finding note), includes `uncertainty` from provider in response, deduplicated `citations` (input.url + provider.citations with `dict.fromkeys` preservation order), adds new `llm_provider` field, emits `SubmissionAIAnalyzeRequested` outbox event, and calls `_embed_text('submissions', o.id, query)` to seed cache. `status` still flips only on *published* public-evidence match (not on LLM output). Escalations still 100% human-button triggered, no AI auto-escalation.
  - Updated `POST /analyst/search` — If `sort_by == 'semantic'` (or sort_by='relevance' as alias) + q present, computes `q_vec = emb.embed(q)`. For each of the 5 collections, first recalls top K=`max(4*limit,100)` candidates by creation_time (SQLite MVP can't use pgvector ANN), then passes rows through `_semantic_rerank` to cosine-rescore + cut to `limit`. Result items carry `semantic_score` float; response envelope's `sort` now includes `{semantic: bool, embedding_provider: name or None}`; each per-collection bag includes new `semantic_reranked: bool` flag. Filter facets (`statuses/review_statuses/uncertainty/source_statuses`) unchanged. RBAC ANALYST+ preserved.
- **worker.py** — Added `AI_PREFIXES = ("SubmissionAI", "AI_", "DocumentAI", "EvidenceAI")` and `_apply_bounded_ai_job(event)` handler, invoked from `_process_event_fields()` right before `DISPATCHED` commit. On AI-prefixed events, handler does lazy imports of `get_*_provider`, re-runs factory selection to pick up env changes, emits an audit row `AIEVENT_{event_type}` with `actor='ai-worker/{llm.name}'` so AI-bounded actions are attributionally distinct from human reviewers. Transactionally committed per event. Provider failures never mark event DEAD; they simply skip audit and continue with normal dispatch, keeping worker resilient.
- **.env.example** fully populated with all new env keys: `OLLAMA_URL`, `OLLAMA_LLM_MODEL`, `OLLAMA_EMB_MODEL`, `HF_API_TOKEN`, `HF_LLM_MODEL`, `HF_EMB_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `AI_TIMEOUT_SECONDS`, `WORKER_DISABLED`, `SCHEDULER_DISABLED`, `WORKER_NAME`, `WORKER_POLL_SECONDS`. Existing keys (DATABASE_URL, REDIS_URL, LLM_PROVIDER, EMBEDDING_PROVIDER, AUTH_SECRET) preserved.
- **Validations:**
  - pytest 24/24 green (10.84s, only 2 framework deprecation warnings for httpx2 + anyio.BlockingPortal)
  - Alembic upgrade head --sql offline validated against `DATABASE_URL=postgresql+psycopg://aipeiisr:development-only@localhost:5432/aipeiisr`: `PostgresqlImpl` context selected, both 0001 and 0002 emit valid DDL including TIMESTAMP WITH TIME ZONE, UniqueConstraint on evidence_relations, CREATE UNIQUE INDEX ix_documents_content_hash, UPDATE alembic_version='0002_knowledge_layer'.
  - Providers import shape check: all 6 adapter classes instantiate offline (Mock default); invalid-kind factory inputs always downgrade → Mock without throwing.
- **Dependencies:** No new pip packages (Ollama/HF/OpenRouter adapters use stdlib urllib.request, no httpx/requests added beyond what's already in requirements.txt). Only 4 previously-missing packages now installed in existing venv from requirements.txt: redis, alembic, Mako, MarkupSafe. psycopg[binary] already present.

## 2026-09-22 (Session 4 — Phase 3 Frontend Scaffolds v0.5.1)
- **CITIZEN PAGE:** Added Published Evidence browser section below submission form. Unwraps GET /public/evidence paginated envelope {items, total, limit, offset}. Added search input (q param) + 3 sort chips (newest/oldest/cited, default cited). Each evidence card renders review_status badge, cited_by_count count badge, source_url external link, excerpt, and findings[] chip array cross-linked to /findings/:id.
- **SITUATION ROOM:** Rewrote Overview TypeScript type from `sources:number` (flat int) to `sources:{total,draft,disabled,approved}` SourcesDict to match API v0.5.0 contract. Expanded metric grid from 6 cards to 11: added Published findings, Public evidence, Evidence awaiting review, Evidence citation links, Citizen submissions, Escalation rate (with x suffix). Added dedicated SOURCE GOVERNANCE block with 4-cell SubCard subgrid (Total, Approved green, Draft amber, Disabled red) + helper text explaining DRAFT/DISABLED ingestion gating. Card component accepts optional suffix prop.
- **FINDINGS DETAIL ROUTE:** Scaffolded app/findings/[id]/page.tsx at /findings/:id. Calls GET /findings/:fid with x-role=ANALYST header. Renders status pill, finding label, finding ID + investigation ID metadata. Background card with status/investigation/submission timestamps. Linked evidence list reuses citizen evidence-card styling. Version history timeline with vN version-tag chips (v1 emphasized with v-head), status pill per version, actor, timestamp, and release note.
- **SOURCE GOVERNANCE ADMIN ROUTE:** Scaffolded app/admin/sources/page.tsx at /admin/sources. Register new source form (name + URL) that POSTs /sources with DRAFT default. Status filter chip bar with live counts per status (ALL/APPROVED/DRAFT/DISABLED/RETIRED). Sources table with columns: Source (name + id + URL + collector), Status (tone-coded pill), Cadence, Last ingest, Governance actions (Approve / Disable / Reset to draft / Run-once per row with busy-state disable). Row actions call POST /sources/:sid/status and POST /sources/:sid/run-once with x-role=ADMIN header.
- **STYLES.CSS overhaul:** Added filters bar layout + sortbar flex. Added chip and chip-on pill button styles. Added evidence-list + evidence-card layouts: evidence-meta row, cited-badge count pill, source-link external style, excerpt whitespace-preserving paragraph, findings-row dashed separator + finding-chip link buttons. Added sources-block section wrapper, subgrid 4-col responsive layout, SubCard tone variants (tone-good green, tone-warn amber, tone-bad red, tone-neutral slate). Added sources-table with sticky header styling + status-pill color variants per status. Added version-list timeline with version-item left-border bars, v-head accent, version-tag chips, version-meta + version-note typography. Mobile breakpoints: subgrid collapses to 2 columns under 600px.
- Validations: tsc --noEmit 0 errors across all 4 page components + 2 shared layout files. pytest 24/24 green (no backend changes, 0 regressions).

## 2026-09-22 (Session 3 — Knowledge Layer v0.5.0)
- API v0.5.0 bump.
- Added 2 new ORM tables in db.py: FindingVersion {id,finding_id FK,version,label,status,actor,note,created_at} with index on finding_id; EvidenceRelation {id,source_evidence_id FK,target_evidence_id FK,relation_type,rationale,created_at} with UniqueConstraint(source,target,type) + two FK indices.
- Added Alembic revision 0002_knowledge_layer.py with upgrade/downgrade for finding_versions and evidence_relations tables.
- SOURCE GOVERNANCE: POST /sources now creates sources with status DRAFT (was APPROVED). ADMIN only.
- SOURCE GOVERNANCE: added POST /sources/:sid/status (admin, SourceStatusIn) to advance DRAFT→APPROVED→DISABLED→RETIRED; writes SOURCE_STATUS_{old}_TO_{new} audit row and emits SourceAPPROVED / SourceDISABLED outbox events.
- SOURCE GOVERNANCE: GET /sources/:sid detail view returns {source, recent_documents (last 5), audit (SOURCE_* actions)}.
- SOURCE GOVERNANCE: POST /sources/:sid/collect-fixture now gates ingestion with 409 Source status {DRAFT,DISABLED} blocks ingestion. Scheduler tick similarly skips non-APPROVED sources.
- SOURCE GOVERNANCE: POST /sources/:sid/run-once returns 404 Source not found or disabled when not APPROVED (scheduler.run_source_now False path).
- EVIDENCE CITATION GRAPH: added Pydantic schema EvidenceRelationIn {target_evidence_id, relation_type=CORROBORATES, rationale?}.
- EVIDENCE CITATION GRAPH: added POST /evidence/:eid/relations (ANALYST) — creates EvidenceRelation; guard 422 self-reference, guard 409 duplicate relation (UQ); returns {relation, direction_label}.
- EVIDENCE CITATION GRAPH: added GET /evidence/:eid/relations (ANALYST) — returns {outgoing, incoming, citation_counts{cited_by, cites, linked_investigations}} with per-row direction_label (CORROBORATES/CONTRADICTS/RELATED_TO with incoming arrow).
- EVIDENCE CITATION GRAPH: added GET /graph/evidence (ANALYST) — returns {nodes, edges} dump of all evidence relations, node labels are evidence excerpt first 40 chars.
- PUBLICATION RELEASE: POST /findings/:iid/publish changed return contract from bare finding to envelope {finding, version@v1}. FindingVersion.version=1 inserted atomically with Finding mutation + investigation→PUBLISHED transition.
- PUBLICATION RELEASE: added POST /findings/:fid/update (PUBLISHER/ADMIN, FindingUpdateIn {label,summary?}) — increments FindingVersion.version via SELECT MAX(version)+1 in same tx, updates Finding.label and/or Finding.summary, writes FINDING_UPDATED audit + FindingUpdated outbox.
- PUBLICATION RELEASE: added POST /findings/:fid/unpublish (PUBLISHER/ADMIN, FindingUnpublishIn {note ≥3 chars}) — sets Finding.status=UNPUBLISHED, inserts FindingVersion with that status and note, resets Investigation.status=UNDER_INVESTIGATION, writes FINDING_UNPUBLISHED audit + FindingUnpublished outbox.
- PUBLICATION RELEASE: findings list now role-gated (citizen/anon sees PUBLISHED only, others see all); findings detail embeds versions[] history with role-gated visibility matching list.
- INVESTIGATIONS: GET /investigations/:id detail view now embeds findings[] WITH versions[] per finding (version list visible to ANALYST+/admin).
- ANALYST STRUCTURED SEARCH: added Pydantic schemas AnalystSearchIn (5 collection flags, 12 filter dimensions, limit/offset) and AnalystSearchPerCollection (items[],total).
- ANALYST STRUCTURED SEARCH: added POST /analyst/search (ANALYST+ only) — pivots findings/investigations/evidence/claims/documents with per-collection filters, returns {query,collections,facets,results} where results is keyed per-collection with {items,total}. Each row enriched with count fields (finding_count, evidence_count, cited_by, investigation_count, claim_count, source_name, submission_id, version_count) via scalar subqueries. Facets aggregates: statuses (per status counts), review_statuses, uncertainty (per bucket), source_statuses.
- PUBLIC EVIDENCE: sort=cited added — orders by cited_by_count DESC using GROUP BY evidence_relations.target_evidence_id with COALESCE outerjoin. Each item now carries cited_by_count plus findings[] array (all published findings linked via investigation_evidence).
- PUBLIC FINDINGS: each item enriched with evidence_count (count of public evidence linked through investigation_evidence → evidence) plus public_evidence[] subarray (3 items max) for quick inline rendering.
- ROOM OVERVIEW: added sources dict {total,draft,disabled,approved} (4 count queries) and evidence_relations count so situation room can show graph health.
- AUDIT: added entity filter so /audit?entity=:sid retrieves only audit rows for that entity (used by source detail view).
- Bugfix: Pydantic v2 BaseModel.model_dump() does not accept field override kwargs. Changed create_source from b.model_dump(status='DRAFT') to {**b.model_dump(),'status':'DRAFT'}.
- Bugfix: Evidence relations UniqueConstraint failure wrapped in try/except + rollback before HTTPException 409 duplicate relation.
- Bugfix: Findings version increment uses tx-scalar SELECT MAX(version) + 1 + flush to avoid race and guarantee sequential version numbers.
- Tests: Added 6 new integration tests in test_workflow.py:
  - test_analyst_structured_search_rbac_and_facets — 403 anon, 200 analyst, shape {query,collections,facets,results}, 4 facets present, 5 collections have items+total, status filter applied.
  - test_evidence_citation_graph_and_relations — create 2 evidences, POST CORROBORATES, duplicate 409, self-reference 422, /relations view has citation_counts≥1, /graph/evidence has nodes+edges≥1.
  - test_publication_release_lifecycle_update_unpublish_versions — publish v1 → update label v2 → unpublish v3, versions history≥3, citizen 403 on UNPUBLISHED finding detail, investigation reset.
  - test_source_governance_approval_disable_and_ingestion_gating — DRAFT default→collect 409→APPROVE→collect 201→DISABLE→collect 409, detail has audit, analyst POST /sources 403.
  - test_public_evidence_cited_sort_and_findings_version_visibility — published evidence linked to published finding, sort=cited returns cited_by_count populated, items have findings[] enrichment, /public/findings have evidence_count.
- Tests: Refactored 5 existing tests for new DRAFT-source contract (append status→APPROVED call after create_source): test_approved_fixture_source_creates_then_dedupes_document, test_scheduler_tick_and_run_once, test_document_evidence_projection_links_claims_and_evidence, test_document_chain_endpoint_and_internal_search.
- Tests: Refactored test_investigation_detail_and_finding_detail_endpoints to unwrap publish envelope {finding,version} into f=pr['finding'] before GET /findings/:fid.
- Full test suite: 24/24 pytest passing. tsc --noEmit 0 errors. VSCode diagnostics 0 issues.

## 2026-09-22 (Session 2 - Second Delivery — Phase 1 completion + Phase 2 start)
- API v0.4.0 bump.
- Worker lifecycle: added list_dead_events / retry_dead_event / retry_all_dead / get_event / cancel_event utilities in worker.py.
- Outbox admin endpoints: GET /operations/outbox/{id}, POST /operations/outbox/{id}/cancel, POST /operations/outbox/{id}/retry, GET /operations/outbox-dlq, POST /operations/outbox-dlq/retry.
- Added filters (status, event_type, action, actor, public, review_status, claim_id, source_id, limit/offset, sort) across all list endpoints: documents, claims, evidence, investigations, audit, outbox, public evidence, public findings, public search.
- Public evidence projection: paginated envelope (items/total/limit/offset), sort newest/oldest, per-item findings cross-linked via investigation_evidence → findings join.
- Added GET /public/findings paginated endpoint.
- Rewrote /public/search to return counts envelope with query echo + findings/evidence buckets.
- Added GET /documents/{id}/chain: source → document → claims → evidence → investigation_evidence → investigations → findings full knowledge graph traversal.
- Added POST /internal/search role-gated multi-faceted search (q, statuses, investigation_id, submission_id) returning documents/claims/evidence/investigations with nested findings and submissions.
- Added GET /investigations/{id} detail view with submission + evidence + findings.
- Added GET /findings/{id} public detail view with investigation + linked evidence.
- Added GET /evidence/{id}/investigations reverse evidence-to-investigation lookup.
- Added GET /documents/{id} and GET /evidence paginated list.
- Extended /room/overview with 12 metrics: public/internal evidence counts, published findings, citizen submissions, workflow submissions-to-escalations ratio.
- Added 7 new tests: DLQ/retry/cancel lifecycle; public evidence pagination+sort+findings; public findings/search; document chain + internal search RBAC; investigation/finding detail; room overview + endpoint filters.
- Adapted existing public evidence test from list contract to paginated envelope contract.
- Full suite 19/19 passing. TypeScript frontend tsc --noEmit clean. VSCode diagnostics clean.

## 2026-09-22 (Session 2 - First Delivery)
- Created persistent autonomous build controls.
- Recorded provider research and selected safe local fallbacks.
- Added provider interfaces and a citizen-facing Next.js fact-check scaffold.
- Replaced in-memory P0 workflow data with persistent SQLAlchemy SQLite development records.
- Added safe synthetic source collection, document hashing/deduplication and claim creation.
- Added evidence records, evidence-to-investigation rationale links and operational overview API.
- Added Docker Compose PostgreSQL/Redis integration contract and required documentation structure.
- Added analyst Situation Room overview frontend route and responsive operational metric cards.
- Added persistent transactional outbox events and development dispatcher for workflow events.
- Added explicit public evidence and public search projections; internal evidence remains role restricted.
- Added qualified citizen submission matching against human-reviewed public evidence only.
- Added verified Bearer-role middleware and analyst-only internal finding detail route.
- Configured Alembic with versioned migrations; initial revision 0001_initial covers all 10 tables.
- Added Redis streams consumer with consumer groups, 5-attempt retry, DLQ and automatic in-process DB fallback when Redis unavailable.
- Added background worker daemon loop (WORKER_DISABLED=1 for tests) with admin status/tick endpoints.
- Added source scheduler: interval-based ticking loop, RSS collection hooks (gated to APPROVED sources), per-source run-once endpoint, admin status/tick.
- Added /documents/{id}/evidence projection joining claims + evidence by claim_id and source_url.
- Enhanced /health to report worker status, scheduler status and inventory counts.
- Added /sources/{id}/run-once and /operations/{scheduler,worker}/{status,tick} admin endpoints.
- Added conftest.py isolating tests: DATABASE_URL temp file per run, WORKER_DISABLED and SCHEDULER_DISABLED env gating.
- Added 6 new tests covering health payload shape, worker RBAC + tick, scheduler RBAC + tick + run-once, document-evidence projection RBAC + linking.
- Validated frontend: pnpm install completes supply-chain lockfile policy; tsc --noEmit clean; sharp build-scripts gate is informational.
