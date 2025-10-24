# AppDiscovery

> Complete app store intelligence platform with CLI, REST API, and web dashboard

Multi-agent system for discovering, analyzing, and understanding mobile apps across app stores. Built with evidence-first principles—all data is cached, tracked, and linked to sources.

## Features

✅ **Ingest Agent** - Search and fetch Apple App Store metadata + reviews
✅ **Signals Agent** - Compute traction metrics (review velocity, text density, rating trends)
✅ **REST API** - FastAPI backend with endpoints for apps, reviews, and signals
✅ **Web Dashboard** - Beautiful UI for browsing apps and analyzing data
✅ **HTTP Caching** - SHA256-based caching with rate limiting
✅ **Evidence Bundles** - All data linked to source URLs with timestamps

## Quick Start

### 1. Installation

```bash
# Clone and install
git clone https://github.com/yourusername/appdiscovery.git
cd appdiscovery

# Install dependencies
pip install sqlmodel sqlalchemy pydantic pydantic-settings requests typer rich fastapi uvicorn

# Or with poetry
poetry install

# Initialize database
python -m apps.ingest.cli init
```

### 2. Discover Apps

```bash
# Search Spanish finance apps
python -m apps.ingest.cli discover \
  --store apple \
  --lang es \
  --country ES \
  --q "gastos" \
  --limit 50

# Japanese budget apps
python -m apps.ingest.cli discover \
  --store apple \
  --lang ja \
  --country JP \
  --q "家計簿" \
  --limit 50
```

### 3. Enrich with Details & Reviews

```bash
# Enrich apps discovered today
python -m apps.ingest.cli enrich \
  --since 2025-10-24 \
  --country US \
  --lang en \
  --compute-signals

# Or enrich specific apps
python -m apps.ingest.cli enrich \
  --app-ids 300238550 \
  --compute-signals
```

### 4. Start the API

```bash
# Start FastAPI server
python -m apps.api.main

# Or with uvicorn
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the Dashboard

```bash
# Open in browser
open http://localhost:8000/docs  # API documentation
open web/static/index.html      # Dashboard (or serve with any HTTP server)

# Serve dashboard with Python
cd web/static && python -m http.server 3000
# Then open http://localhost:3000
```

## Dashboard Preview

The web dashboard provides:
- **Real-time stats** - Total apps, reviews, evidence bundles
- **App browsing** - Filter by store, category with beautiful cards
- **Detailed views** - Full app info, descriptions, signals, recent reviews
- **Traction metrics** - Review windows (7d/30d), rating velocity, text density

## REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info and endpoint list |
| `GET /stats` | Platform statistics |
| `GET /stores` | List all app stores |
| `GET /apps` | List apps with filters |
| `GET /apps/{id}` | Get app details |
| `GET /apps/{id}/reviews` | Get app reviews |
| `GET /apps/{id}/signals` | Get/compute signals |

### Example API Calls

```bash
# Get stats
curl http://localhost:8000/stats | jq

# List apps
curl "http://localhost:8000/apps?store=apple&limit=10" | jq

# Get app details
curl http://localhost:8000/apps/1 | jq

# Compute signals
curl "http://localhost:8000/apps/1/signals?recompute=true" | jq
```

## CLI Commands

### discover

Search app stores and persist metadata.

```bash
python -m apps.ingest.cli discover \
  --store apple \
  --lang es \
  --country MX \
  --q "finanzas" \
  --limit 100
```

**Options:**
- `--store`: Store to search (currently only `apple`)
- `--lang`: Language code (e.g., `es`, `ja`, `pt`)
- `--country`: Country code (e.g., `ES`, `MX`, `JP`)
- `--q`: Search query (required)
- `--limit`: Max results per query (default: 50)

### enrich

Fetch full details, descriptions, and reviews.

```bash
python -m apps.ingest.cli enrich \
  --since 2025-10-24 \
  --country US \
  --lang en \
  --compute-signals
```

**Options:**
- `--since`: Enrich apps seen since date (YYYY-MM-DD)
- `--app-ids`: Specific app IDs to enrich (can specify multiple)
- `--country`: Country for details/reviews (default: US)
- `--lang`: Language for details/reviews (default: en)
- `--compute-signals`: Compute traction metrics (default: false)

### init

Initialize the database schema.

```bash
python -m apps.ingest.cli init
```

## Architecture

### Multi-Agent Design

Each agent is specialized with clear boundaries:

1. **Ingest Agent** (`apps/ingest/`)
   - Search, fetch, cache app data
   - Idempotent upserts by (store_id, store_app_id)
   - Rate limiting: 2 req/s default

2. **Signals Agent** (`apps/core/signals.py`)
   - Compute review windows (7d, 30d)
   - Rating velocity (day-over-day)
   - Text density (description length)

3. **API Layer** (`apps/api/`)
   - FastAPI REST endpoints
   - JSON responses with CORS support
   - Swagger docs at `/docs`

4. **Web Dashboard** (`web/static/`)
   - Vanilla HTML/CSS/JS (no frameworks)
   - Responsive design
   - Real-time API integration

### Data Flow

```
CLI discover → Search API → Cache → Database (apps, app_locales, daily_snapshots)
                                ↓
CLI enrich → Details API → Cache → Database (reviews, evidence)
                                ↓
Signals Agent → Compute metrics → Store in evidence.lang_detect
                                ↓
API → Query database → JSON responses
                                ↓
Dashboard → Fetch API → Display UI
```

### Database Schema

**Tables:**
- `stores` - App store metadata (apple, google_play)
- `apps` - Core app records
- `app_locales` - Localized titles/descriptions
- `reviews` - Individual reviews
- `daily_snapshots` - Daily rating aggregates
- `evidence` - Evidence bundles with source URLs

See `docs/data_model.md` for details.

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
# Database
DATABASE_URL=sqlite:///./data/appdiscovery.db

# Cache
CACHE_DIR=./data/cache
CACHE_TTL_SECONDS=86400

# Rate limiting
RATE_LIMIT_REQUESTS_PER_SECOND=2.0
RATE_LIMIT_BURST=5

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Development

### Project Structure

```
AppDiscovery/
├── apps/
│   ├── core/           # Shared infrastructure
│   │   ├── config.py   # Settings management
│   │   ├── db.py       # Database session factory
│   │   ├── models.py   # SQLModel ORM models
│   │   └── signals.py  # Traction metrics computation
│   ├── ingest/         # Ingest agent
│   │   ├── cli.py      # Typer CLI
│   │   ├── cache.py    # HTTP cache + rate limiting
│   │   ├── types.py    # Pydantic types
│   │   └── fetchers/   # Store-specific fetchers
│   └── api/            # REST API
│       └── main.py     # FastAPI application
├── web/
│   └── static/
│       └── index.html  # Web dashboard
├── prompts/            # Agent specifications
├── docs/               # Documentation
└── infra/
    └── migrations/     # SQL migrations
```

### Running Tests

```bash
# Run all tests (skips smoke tests by default)
pytest

# Run smoke tests (hits real APIs but uses cache)
RUN_SMOKE_TESTS=true pytest apps/ingest/tests/test_ingest_smoke.py -v

# Run with coverage
pytest --cov=apps --cov-report=html
```

### Global Policies

All operations follow these principles:

- **Evidence over opinion** - No invented data
- **Respect store TOS** - Official APIs only
- **Idempotent by default** - Safe to re-run
- **Cost-aware** - Aggressive caching
- **No PII** - Only public review names
- **Security** - No secrets in code

See `prompts/policies.md` for details.

## Use Cases

### 1. Market Research

Discover trending apps in specific locales/categories:

```bash
# Mexican fintech apps
python -m apps.ingest.cli discover --lang es --country MX --q "finanzas" --limit 200
python -m apps.ingest.cli enrich --since 2025-10-24 --compute-signals

# View in dashboard
open http://localhost:3000
```

### 2. Competitive Analysis

Track rating velocity and review sentiment:

```bash
# Enrich competitor apps
python -m apps.ingest.cli enrich --app-ids 123456789 --app-ids 987654321 --compute-signals

# Query signals via API
curl "http://localhost:8000/apps/1/signals" | jq '.signals'
```

### 3. Localization Research

Analyze app descriptions across languages:

```bash
# Fetch multiple locales
python -m apps.ingest.cli enrich --since 2025-10-24 --country ES --lang es
python -m apps.ingest.cli enrich --since 2025-10-24 --country JP --lang ja

# Compare via API
curl "http://localhost:8000/apps/1" | jq '.locales'
```

## Signals Explained

### Review Windows

- **review_7d**: Number of reviews in past 7 days
- **review_30d**: Number of reviews in past 30 days

Indicates recent user engagement and app activity.

### Rating Velocity

- **rating_velocity_d1**: Day-over-day change in total ratings

Positive velocity = growing user base. Requires two consecutive daily snapshots.

### Text Density

- **text_density**: Character count of app description

Longer descriptions may indicate more mature/feature-rich apps. Uses longest non-English description if available.

## Limitations

- **Google Play**: Not implemented (spec ready in `prompts/agents/ingest_agent.md`)
- **Translation**: Not implemented (spec ready in `prompts/agents/translate_agent.md`)
- **Real-time monitoring**: Daily/weekly updates recommended, not real-time
- **App Store Coverage**: Apple only (Google Play requires compliance checks)

## Troubleshooting

### Database errors

```bash
# Reset database
rm -f data/appdiscovery.db
python -m apps.ingest.cli init
```

### API connection errors

```bash
# Check if API is running
curl http://localhost:8000

# Start API with verbose logs
uvicorn apps.api.main:app --reload --log-level debug
```

### Cache issues

```bash
# Clear cache
rm -rf data/cache/*

# Check cache stats
ls -lh data/cache/ | wc -l
```

## Contributing

1. Follow the agent architecture - each agent owns specific files
2. Add tests for new functionality
3. Update `prompts/io_schemas.md` when adding new data structures
4. Run formatters before committing:
   ```bash
   black apps/ --line-length 100
   ruff check apps/ --fix
   ```

## Future Work

### Translation Agent (Week 2)
- Provider-agnostic translation (DeepL, OpenAI)
- Hash-based deduplication
- Chunking for long descriptions
- See `prompts/agents/translate_agent.md`

### Google Play Support
- Currently gated behind `compliance_ok` flag
- Requires careful rate limiting and user agent
- See `prompts/agents/ingest_agent.md`

### Enhanced Dashboard
- Charts and graphs (signals over time)
- Bulk export to CSV/JSON
- Advanced filtering and search
- User authentication

## License

MIT

---

**Built with Claude Code** 🤖 - A multi-agent approach to app intelligence

[Documentation](docs/) | [API Docs](http://localhost:8000/docs) | [Dashboard](http://localhost:3000)
