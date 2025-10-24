# Principles

## Core Philosophy

**Evidence over opinion.** AppDiscovery is a retrieval-first system. LLMs reason only over evidence that has been pulled, cached, and persisted by our code. We do not invent data.

## Design Principles

### 1. Agent Specialization

Each agent has:
- A **clear role** with specific responsibilities
- **Allowed files** it can create/modify (see `prompts/agents.md`)
- **Never touches** files owned by other agents

This ensures:
- Clean separation of concerns
- Easy to reason about changes
- Safe parallel development

### 2. Idempotency

All operations must be safe to re-run:
- **Upserts**, not inserts (use unique constraints)
- **Caching** prevents duplicate network calls
- **Migrations** use `IF NOT EXISTS` or equivalent

Running the same command twice should:
- Produce the same database state
- Use cached data (no redundant API calls)
- Be fast on subsequent runs

### 3. Cost Awareness

Track and minimize costs:
- **Cache all HTTP calls** with SHA256 keys
- **Deduplicate translations** by content hash
- **Log estimated costs** (tokens, chars, API calls)
- **Batch operations** where possible

### 4. Respect Store TOS

- Use **official/public APIs** whenever available
- For unofficial endpoints:
  - Gate behind **compliance_ok** flag
  - Implement **strict rate limiting**
  - Use **clear user agent** identifying the project
- **Never bypass** robots.txt or anti-automation

### 5. Privacy and Security

- **No PII** beyond public display names from reviews
- **No secrets in code** - always use environment variables
- **No credential harvesting** - this is a defensive security tool
- **Audit trails** - log all data sources and timestamps

### 6. Observability

- **Structured logging** in JSON format
- **Evidence bundles** link all data to source URLs
- **Timestamps** on every entity (created_at, fetched_at, etc.)
- **Provenance** tracking (translation_provider, etc.)

### 7. Fail Gracefully

- **Null-safe** operations (missing data → null, not exception)
- **Retry with backoff** for transient network errors
- **Degrade gracefully** (e.g., wider time windows if sparse data)
- **Log warnings**, don't crash

## Anti-Patterns

❌ **Inventing data** - Never make up app descriptions, ratings, or reviews

❌ **Hardcoding secrets** - Always use environment variables or secret managers

❌ **Scraping fragile endpoints** - Prefer official APIs; gate unofficial ones

❌ **Ignoring idempotency** - All operations must be re-runnable

❌ **Skipping cache** - Every HTTP call must go through the cache layer

❌ **Cross-agent dependencies** - Agents should be loosely coupled via DB, not direct calls

## Development Workflow

### Vibecoding Loop

1. **Pick an agent** from `prompts/agents.md`
2. **Copy the task prompt** with specific inputs
3. **Implement following constraints** (allowed files, tools, etc.)
4. **Write tests** (smoke tests for API calls, unit tests for logic)
5. **Provide PR diff** with summary and runbook
6. **Update docs** if schemas or workflows changed

### Testing Strategy

- **Smoke tests**: Real API calls (cached) with known app IDs
- **Unit tests**: Pure functions, synthetic data
- **Skip by default**: Use env var `RUN_SMOKE_TESTS=true` for CI

### Git Hygiene

- **One agent per PR** when possible
- **Descriptive commits**: "Add Apple ingest fetcher with caching"
- **Update migrations** if schema changes
- **Keep docs in sync** via docs_agent

## Performance Targets

- **Discover**: 100 apps in <10 seconds (cached: <1 second)
- **Enrich**: 10 apps with details + reviews in <60 seconds (cached: <5 seconds)
- **Translate**: 100 descriptions in <30 seconds (with batching)
- **Signals**: Compute for 1000 apps in <10 seconds

## Future Principles

As the system grows:
- **Scale horizontally**: Use worker pools for parallel ingest
- **Centralize config**: Move from .env to config service
- **Monitor proactively**: Set up alerts for rate limit hits, failed fetches
- **Version evidence**: Keep historical evidence bundles for audits
