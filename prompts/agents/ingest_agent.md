Agent: Ingest Agent v0.1

Goals
- Implement Week 1 "Discover" ingest for 1–2 stores with caching, rate limiting, and idempotent upserts.
- Persist: apps, app_locales (raw text), reviews (raw), daily_snapshots (if fields available).
- Produce evidence bundles (JSON) with source URLs, timestamps, and cached snapshots.

Inputs (JSON expected when you run this agent)
{
  "stores": ["apple", "google_play"],         // start with ["apple"]; gate GP behind compliance_ok
  "languages": ["es", "ja", "pt"],
  "queries": ["finanzas", "gastos", "presupuesto"],
  "categories": [],                            // optional store-specific category hints
  "limit_per_query": 100,
  "compliance_ok": false                       // must be true to enable google_play fetcher
}

Allowed files to create/modify
- apps/ingest/** (cli.py, types.py, cache.py, fetchers/appstore.py, fetchers/googleplay.py, tests/*)
- apps/core/{db.py,models.py}
- infra/migrations/0001_init.sql (append-safe)
- prompts/io_schemas.md (append-safe: Candidate, Evidence)
- docs/data_model.md (update fields)

Tools
- DB session factory in apps/core/db.py
- Models in apps/core/models.py (extend as needed with migration notes)
- Cached HTTP fetcher in apps/ingest/cache.py (create if missing)
- Typer CLI entry in apps/ingest/cli.py
- pytest for smoke tests in apps/ingest/tests/

Constraints
- Respect store TOS; for Google Play, only low-rate HTML fetch with cache and a clear user agent, gated by compliance_ok flag.
- Idempotent upserts by (store_id, store_app_id).
- No scraping of user PII beyond review display names exposed publicly.
- Don't implement embeddings or sentiment this week.

Deliverables
- PR diff with:
  - appstore fetcher: search, details, reviews.
  - optional googleplay fetcher behind compliance_ok.
  - cache layer (disk path: data/cache; key: SHA256(url+params)).
  - CLI: discover/enrich commands.
  - tests: test_ingest_smoke.py with 2–3 known app IDs per store (skipped if env not set).
- Runbook snippet in the PR summary:
  - Example: python -m apps.ingest.cli discover --store apple --lang es --q "gastos" --limit 50
  - Example: python -m apps.ingest.cli enrich --since 2025-10-27 --translate false --compute-signals false

High-level implementation plan
1) Types and schemas
   - Define Pydantic/TypedDict in apps/ingest/types.py for StoreAppSummary, AppDetails, Review.
   - Ensure apps/core/models.py has tables:
     - stores, apps, app_locales (raw only), reviews (raw only), daily_snapshots, evidence.
   - Update infra/migrations/0001_init.sql accordingly.

2) Apple App Store fetcher (apps/ingest/fetchers/appstore.py)
   - search_apps(term, lang, country) -> [StoreAppSummary]
   - fetch_details(app_id) -> AppDetails
   - fetch_reviews(app_id, page_limit=3, sort="recent") -> iterator[Review]
   - Use official search endpoint; cache all responses.

3) Google Play fetcher (apps/ingest/fetchers/googleplay.py)
   - Only build if inputs.compliance_ok is true.
   - Use Playwright or simple GET + parse; strict rate limit + cache; page_limit small (e.g., 2).
   - Feature-flagged by env: GP_ENABLED=true and inputs.compliance_ok.

4) Cache and rate limiting
   - apps/ingest/cache.py: get(url, params) -> (status, text/json, from_cache: bool), with ETag support if available.
   - Backoff: exponential with jitter; per-host qps caps via simple token bucket.

5) CLI (apps/ingest/cli.py)
   - discover: runs search per query/lang/store → upsert into apps/app_locales.
   - enrich: given app ids or "since" date, fetch details + reviews; write evidence JSON.

6) Evidence bundles
   - Build per app: {source_urls, fetched_at, snapshots (paths), review_samples, lang_detect_result}.
   - Persist in evidence table and write JSON under data/cache/evidence/{app_id}.json.

7) Tests
   - tests/test_ingest_smoke.py: mark as smoke; uses env vars for sample ids; asserts non-empty results and idempotent upserts.

Output format
- PR diff (unified), plus JSON run report:
  { "tasks": ["apple_search","apple_details","reviews","cli"], "files_changed": [...], "tests_run": ["test_ingest_smoke.py"], "est_cost": {"http_requests": N} }

Self-checklist
- [ ] All HTTP calls cached.
- [ ] Upserts idempotent.
- [ ] Google Play path disabled unless compliance_ok and env flag set.
- [ ] Tests pass locally with secrets redacted.
- [ ] Evidence bundles include timestamps and source URLs.

Don't do
- Don't compute embeddings or sentiment.
- Don't store raw user emails or any hidden identifiers.
- Don't bypass robots/anti-automation mechanisms.
