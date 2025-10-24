# AppDiscovery

Multi-agent app store intelligence platform. Discover, analyze, and understand mobile apps across app stores using retrieval-first, evidence-based workflows.

## Overview

AppDiscovery is designed to help you:
- **Discover** apps from Apple App Store (and Google Play with compliance checks)
- **Ingest** app metadata, reviews, and ratings with automatic caching
- **Translate** content across languages (coming soon via translate_agent)
- **Compute signals** like review velocity, rating trends (coming soon via signals_agent)
- **Build evidence bundles** for downstream analysis

### Architecture

The system uses a **multi-agent architecture** where specialized agents handle specific tasks:

1. **Ingest Agent** (✅ implemented) - Search, fetch, cache app data
2. **Translate Agent** (📋 spec ready) - Provider-agnostic translation
3. **Signals Agent** (📋 spec ready) - Compute traction metrics
4. **Reviewer Copilot** (🔜 planned) - Draft rationales from evidence
5. **Docs Agent** (🔜 planned) - Keep documentation in sync

See `prompts/agents.md` for the complete agent registry.

## Quick Start

### Prerequisites

- Python 3.10+
- Poetry (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/appdiscovery.git
cd appdiscovery

# Install dependencies with Poetry
poetry install

# Or with pip
pip install -e .

# Copy environment template
cp .env.example .env

# Initialize database
poetry run python -m apps.ingest.cli init
```

### Basic Usage

#### 1. Discover apps by search

```bash
# Search Apple App Store for budget apps in Spanish (Spain)
poetry run python -m apps.ingest.cli discover \
  --store apple \
  --lang es \
  --country ES \
  --q "gastos" \
  --limit 50
```

#### 2. Enrich apps with details and reviews

```bash
# Enrich apps discovered since Oct 24
poetry run python -m apps.ingest.cli enrich \
  --since 2025-10-24 \
  --country ES \
  --lang es

# Or enrich specific app IDs
poetry run python -m apps.ingest.cli enrich \
  --app-ids 300238550 \
  --app-ids 1010865877
```

#### 3. View evidence bundles

```bash
# Evidence bundles are saved to data/cache/evidence/{app_id}.json
cat data/cache/evidence/1.json | jq
```

## Runbook

### Discovery Workflow

**Goal:** Find candidate apps in specific markets/languages

```bash
# Example: Mexican finance apps
poetry run python -m apps.ingest.cli discover \
  --store apple \
  --lang es \
  --country MX \
  --q "finanzas" \
  --limit 100

poetry run python -m apps.ingest.cli discover \
  --store apple \
  --lang es \
  --country MX \
  --q "presupuesto" \
  --limit 100

# Japanese finance apps
poetry run python -m apps.ingest.cli discover \
  --store apple \
  --lang ja \
  --country JP \
  --q "家計簿" \
  --limit 100
```

**Output:** Apps are persisted to database with:
- Core app record (store, store_app_id, bundle_id)
- Locale-specific metadata (title, description in original language)
- Daily snapshot (rating count, avg rating)

### Enrichment Workflow

**Goal:** Get full details, descriptions, and recent reviews

```bash
# Enrich all apps discovered in last week
poetry run python -m apps.ingest.cli enrich \
  --since $(date -d '7 days ago' +%Y-%m-%d) \
  --country US \
  --lang en

# Enrich with Spanish locale
poetry run python -m apps.ingest.cli enrich \
  --since 2025-10-24 \
  --country ES \
  --lang es
```

**Output:**
- Updated app_locales with full description
- Reviews (up to 3 pages, ~150 reviews per app)
- Evidence bundle JSON with source URLs and review samples

### Testing

```bash
# Run all tests (skips smoke tests by default)
poetry run pytest

# Run smoke tests (hits real APIs but uses cache)
RUN_SMOKE_TESTS=true poetry run pytest apps/ingest/tests/test_ingest_smoke.py -v

# Run with coverage
poetry run pytest --cov=apps --cov-report=html
```

### Database

The system uses SQLite by default (`data/appdiscovery.db`). For production, switch to PostgreSQL:

```bash
# In .env
DATABASE_URL=postgresql://user:pass@localhost/appdiscovery

# Run migrations manually (or use SQLModel's create_all for dev)
sqlite3 data/appdiscovery.db < infra/migrations/0001_init.sql
```

**Schema:** See `apps/core/models.py` or `infra/migrations/0001_init.sql`

Tables:
- `stores` - App store metadata
- `apps` - Core app records (unique per store + store_app_id)
- `app_locales` - Localized titles, descriptions (raw + translated)
- `reviews` - Individual reviews (raw + translated)
- `daily_snapshots` - Daily rating aggregates
- `evidence` - Evidence bundles with source URLs

### Caching

All HTTP requests are cached to `data/cache/` using SHA256 keys:
- Cache TTL: 24 hours (configurable via `CACHE_TTL_SECONDS`)
- Cache structure: `data/cache/{first_2_chars}/{sha256}.json`
- Rate limiting: 2 req/s per host (configurable)

To force refresh:
```bash
# Clear cache for a fresh fetch
rm -rf data/cache/*
```

### Evidence Bundles

Evidence bundles are JSON files containing:
- `app_id` - Internal app ID
- `store_app_id` - Platform-specific ID
- `source_urls` - List of API endpoints used
- `review_samples` - Up to 10 recent reviews with rating, date, body
- `fetched_at` - Timestamp

Location: `data/cache/evidence/{app_id}.json`

Example:
```json
{
  "app_id": 1,
  "store_app_id": "300238550",
  "source_urls": [
    "https://itunes.apple.com/lookup?id=300238550",
    "https://itunes.apple.com/rss/customerreviews/id=300238550"
  ],
  "review_samples": [
    {
      "rating": 5,
      "created_at": "2025-10-20T14:23:00",
      "body_raw": "Great app for budgeting!",
      "locale": "en-US"
    }
  ],
  "fetched_at": "2025-10-24T10:30:00"
}
```

## Development

### Project Structure

```
AppDiscovery/
├── apps/
│   ├── core/           # Shared infrastructure
│   │   ├── config.py   # Settings management
│   │   ├── db.py       # Database session factory
│   │   └── models.py   # SQLModel ORM models
│   ├── ingest/         # Ingest agent
│   │   ├── cli.py      # Typer CLI
│   │   ├── cache.py    # HTTP cache + rate limiting
│   │   ├── types.py    # Pydantic types
│   │   ├── fetchers/   # Store-specific fetchers
│   │   └── tests/      # Smoke tests
│   ├── api/            # Future REST API
│   └── worker/         # Future background jobs
├── prompts/            # Agent specifications
│   └── agents/         # Individual agent prompts
├── docs/               # Documentation
├── infra/
│   └── migrations/     # SQL migrations
└── data/               # Local data (gitignored)
    ├── cache/          # HTTP cache
    └── exports/        # Export files
```

### Agent Development

To implement a new agent (e.g., translate_agent):

1. Read the agent spec: `prompts/agents/translate_agent.md`
2. Create allowed files per spec (e.g., `apps/core/translate.py`)
3. Follow constraints (provider-agnostic, cache by hash, etc.)
4. Update `prompts/io_schemas.md` with new schemas
5. Run tests and provide PR diff

See `prompts/agents.md` for the vibecoding loop.

### Global Policies

- **Evidence over opinion** - No invented data, only cached/persisted facts
- **Respect store TOS** - Use official APIs; gate unofficial methods behind compliance flags
- **Idempotent by default** - All operations safe to re-run
- **Cost-aware** - Track token/char usage; cache aggressively
- **No PII** - Only public display names from reviews
- **Security** - No secrets in code; use environment variables

## Future Work

### Translate Agent (Week 2)
- Provider-agnostic translation (DeepL, OpenAI, etc.)
- Hash-based deduplication
- Chunking for long descriptions
- See `prompts/agents/translate_agent.md`

### Signals Agent (Week 2)
- Compute review_7d, review_30d windows
- Rating velocity (day-over-day changes)
- Text density metrics
- See `prompts/agents/signals_agent.md`

### Google Play Support
- Currently gated behind `compliance_ok` flag
- Requires careful rate limiting and user agent
- See `prompts/agents/ingest_agent.md` for constraints

## Contributing

1. Follow the agent architecture - each agent owns specific files
2. Add tests for new functionality
3. Update `prompts/io_schemas.md` when adding new data structures
4. Run `black` and `ruff` before committing

## License

MIT (or your preferred license)

---

**Built with Claude Code** - A multi-agent approach to app intelligence
