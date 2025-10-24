# Policies

Global policies that apply to all agents and operations.

## 1. Evidence Over Opinion

**Policy**: Do not invent data. Never browse the open web directly from an agent unless the task explicitly includes a fetcher and caching layer.

**Implementation**:
- All data must come from official APIs or cached sources
- Log source URLs for every piece of data
- Create evidence bundles linking data to origins
- No LLM-generated "synthetic" app descriptions or reviews

**Violations**:
❌ Generating fake reviews to fill gaps
❌ Inventing app descriptions when API returns null
❌ Estimating ratings without data

## 2. Respect Store TOS

**Policy**: Prefer official/public endpoints. If an endpoint is fragile or unofficial, gate it behind a feature flag and a compliance_ok switch.

**Implementation**:
- Apple: Use iTunes Search API (official, public)
- Google Play: Only with `compliance_ok=true` and `GP_ENABLED=true` env var
  - Low rate (e.g., 1 req/5s)
  - Clear user agent identifying the project
  - HTML fetch only (no automation of user interactions)
- Never bypass robots.txt or rate limits

**Allowed**:
✅ iTunes Search API (official)
✅ iTunes RSS feeds (official)
✅ Google Play public HTML (with compliance_ok flag)

**Prohibited**:
❌ Automated browsing with Selenium/Playwright for interactions
❌ Bypassing CAPTCHAs
❌ Spoofing user agents to evade detection

## 3. Idempotent by Default

**Policy**: All jobs and migrations must be safe to re-run.

**Implementation**:
- Use **upserts** with unique constraints, not raw inserts
- Cache HTTP calls by content hash (identical requests = cache hit)
- Migrations use `CREATE TABLE IF NOT EXISTS` or equivalent
- Running the same command twice produces identical DB state

**Examples**:
✅ `discover` command: Re-running finds same apps, upserts without duplicates
✅ `enrich` command: Re-running uses cache, updates last_seen_at only
✅ Migrations: Safe to run multiple times

## 4. Cost Awareness

**Policy**: Track estimated tokens/characters; cache by content hash.

**Implementation**:
- **HTTP cache**: All GET requests cached for 24h (configurable)
- **Translation cache**: Hash-based dedup (same text + lang + provider = reuse)
- **Batch operations**: Translate 100 strings at once, not 100 API calls
- **Log costs**: Track tokens, chars, API call counts in run reports

**Monitoring**:
- Log cache hit rates
- Estimate costs per run (e.g., "10 API calls, 5000 chars translated")
- Set budgets (future): Fail if exceeds N tokens/day

## 5. Observability

**Policy**: Log structured JSON; zero PII beyond review display names.

**Implementation**:
- Use Python `logging` with JSON formatter (or structured handler)
- Log levels:
  - `INFO`: High-level operations (discovered 50 apps, enriched 10)
  - `WARNING`: Recoverable issues (API 404, cache miss)
  - `ERROR`: Failures that block progress
  - `DEBUG`: Detailed trace (cache paths, response sizes)
- Include:
  - Timestamps (ISO 8601)
  - Operation name (discover, enrich, translate)
  - Counts (apps processed, reviews fetched)
  - Durations (seconds per operation)

**PII Policy**:
✅ Review display names (public, already visible)
❌ Email addresses
❌ IP addresses
❌ User IDs not publicly visible

## 6. Security

**Policy**: No secrets in code. Read from environment or .env.

**Implementation**:
- All API keys via environment variables
- Use `.env` for local dev (gitignored)
- Use secret managers for production (AWS Secrets Manager, etc.)
- Never log secrets (even in debug mode)

**Examples**:
```python
# ✅ Good
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# ❌ Bad
DEEPL_API_KEY = "abc123xyz"
```

## 7. Agent Boundaries

**Policy**: Each agent has allowed files; do not cross boundaries.

**Implementation**:
- See `prompts/agents.md` for allowed paths per agent
- Ingest Agent: `apps/ingest/**`, `apps/core/{db,models}.py`, migrations
- Translate Agent: `apps/core/translate.py`, `apps/core/utils/text.py`
- Signals Agent: `apps/core/signals.py`, models, migrations

**Violations**:
❌ Ingest Agent modifying `apps/core/utils/text.py` (owned by translate_agent)
❌ Signals Agent adding fetchers (owned by ingest_agent)

## 8. Testing

**Policy**: All new functionality must have tests.

**Types**:
- **Smoke tests**: Real API calls (cached) with known app IDs
  - Mark with `@pytest.mark.skipif(os.getenv("RUN_SMOKE_TESTS") != "true")`
  - Use 2-3 well-known apps per store
- **Unit tests**: Pure functions, synthetic data, no network
- **Integration tests**: DB operations with temp SQLite

**Coverage**:
- Aim for >80% coverage on critical paths
- 100% coverage on utils (hashing, chunking, etc.)

## 9. Versioning and Migrations

**Policy**: All schema changes via migrations; never modify past migrations.

**Implementation**:
- New migrations: `infra/migrations/000N_description.sql`
- Append-only: Never edit `0001_init.sql` after first use
- Track version in DB (future): `migrations` table
- Backwards compatible: Add columns as nullable; backfill later

## 10. Rate Limiting

**Policy**: Respect per-host QPS caps; exponential backoff on errors.

**Implementation**:
- Token bucket algorithm in `apps/ingest/cache.py`
- Default: 2 req/s per host, burst of 5
- Backoff: 3 retries with exponential delay (1s, 2s, 4s)
- Status codes for retry: 429, 500, 502, 503, 504

**Configuration**:
```env
RATE_LIMIT_REQUESTS_PER_SECOND=2.0
RATE_LIMIT_BURST=5
```

## Enforcement

- **Code reviews**: Check against these policies before merge
- **Automated checks**: Linters for secrets, tests for idempotency
- **Documentation**: Update `prompts/policies.md` when adding new rules
- **Agent specs**: Reference relevant policies in each agent's prompt
