# Data Model

## Overview

The AppDiscovery data model is designed for:
- **Multi-store** support (Apple, Google Play, future stores)
- **Multi-locale** content with separate raw and translated fields
- **Evidence-based** analysis with audit trails
- **Time-series** tracking via daily snapshots

## Entity Relationships

```
Store (1) ──── (*) App
                    │
                    ├── (*) AppLocale (title, desc in various locales)
                    ├── (*) Review
                    ├── (*) DailySnapshot (rating aggregates over time)
                    └── (*) Evidence (source URLs, cached data)
```

## Tables

### stores

App store metadata.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| name | str | Store identifier ("apple", "google_play") |
| display_name | str | Human-readable name |
| enabled | bool | Whether store is active |
| created_at | datetime | When store was added |

**Indexes:** name (unique)

### apps

Core app records. One per unique (store, store_app_id).

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| store_id | int | Foreign key to stores |
| store_app_id | str | Platform-specific ID (e.g., Apple trackId) |
| bundle_or_package_id | str | Bundle ID (iOS) or package name (Android) |
| developer | str | Developer/publisher name |
| category | str | Primary category |
| first_seen_at | datetime | When first discovered |
| last_seen_at | datetime | When last seen in search |

**Indexes:** (store_id, store_app_id) unique, bundle_or_package_id

**Constraints:** Idempotent upserts on (store_id, store_app_id)

### app_locales

Localized app metadata. Multiple rows per app for different locales.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| app_id | int | Foreign key to apps |
| locale | str | BCP-47 locale code (e.g., "es-MX") |
| title_raw | str | Original title in native language |
| desc_raw | str | Original description |
| title_en | str | English translation (null until translated) |
| desc_en | str | English description translation |
| translation_provider | str | "deepl" \| "llm" \| "null" |
| translated_at | datetime | When translation occurred |
| price | float | App price in this locale |
| currency | str | Currency code |
| countries | JSON | List of countries for this locale |
| updated_at | datetime | Last update timestamp |

**Indexes:** (app_id, locale) unique, locale

**Translation fields:** Only populated after translate_agent runs.

### reviews

Individual app reviews.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| app_id | int | Foreign key to apps |
| store_review_id | str | Platform-specific review ID |
| locale | str | Review language locale |
| rating | int | 1-5 stars |
| title_raw | str | Review title (original language) |
| body_raw | str | Review body (original language) |
| title_en | str | English translation |
| body_en | str | English translation |
| translation_provider | str | Provider used for translation |
| translated_at | datetime | When translated |
| author_name | str | Public display name only |
| created_at | datetime | When review was posted |
| fetched_at | datetime | When we fetched it |

**Indexes:** (app_id, store_review_id) unique, created_at, locale

**Privacy:** Only store public display names; no emails or hidden IDs.

### daily_snapshots

Daily aggregate metrics per app.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| app_id | int | Foreign key to apps |
| date | date | Snapshot date |
| rating_total | int | Total number of ratings |
| rating_count | int | Same as rating_total (compatibility) |
| rating_avg | float | Average rating (1.0-5.0) |
| fetched_at | datetime | When snapshot was taken |

**Indexes:** (app_id, date) unique, date

**Usage:** Used by signals_agent to compute rating velocity (day-over-day changes).

### evidence

Evidence bundles linking apps to source data.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| app_id | int | Foreign key to apps |
| source_urls | JSON | List of API endpoints used |
| cached_paths | JSON | List of cache file paths (relative) |
| review_samples | JSON | Array of {rating, created_at, body_raw, locale} |
| lang_detect | JSON | {detected: str, confidence: float} |
| fetched_at | datetime | When evidence was collected |

**Indexes:** app_id, fetched_at

**Format:** JSON arrays/objects for flexible evidence storage.

## Field Conventions

### Locales

Use BCP-47 format: `{language}-{country}`
- Examples: `en-US`, `es-MX`, `ja-JP`, `pt-BR`

### Raw vs Translated

- **Raw fields** (`title_raw`, `desc_raw`, `body_raw`): Original content in native language
- **Translated fields** (`title_en`, `desc_en`, `body_en`): English translations
- **Provenance**: `translation_provider` and `translated_at` track who translated and when

### Timestamps

- `created_at`: When entity was created in our DB
- `updated_at`: When entity was last modified
- `fetched_at`: When data was retrieved from external source
- `first_seen_at` / `last_seen_at`: Discovery timeline for apps

## Migrations

Schema changes are tracked in `infra/migrations/`:
- `0001_init.sql` - Initial schema (Week 1)
- Future migrations append with incremental numbers

For development, `apps.core.db.init_db()` creates tables from SQLModel metadata.

For production, run migrations manually:
```bash
sqlite3 data/appdiscovery.db < infra/migrations/0001_init.sql
```

## Future Extensions

### Signals Table (Week 2)

| Field | Type | Description |
|-------|------|-------------|
| app_id | int | Foreign key to apps |
| date | date | Signal date |
| review_7d | int | Reviews in past 7 days |
| review_30d | int | Reviews in past 30 days |
| rating_velocity_d1 | int | Day-over-day rating count change |
| text_density | int | Character count of description |
| window_used | str | Which window was used if fallback needed |

### Translation Cache Table (Future)

Hash-based deduplication for translated strings to avoid re-translating identical content.

| Field | Type | Description |
|-------|------|-------------|
| content_hash | str | SHA256 of (original_text + src_lang + tgt_lang + provider) |
| original_text | str | Source text |
| translated_text | str | Translated text |
| src_lang | str | Source language |
| tgt_lang | str | Target language |
| provider | str | Translation provider used |
| created_at | datetime | Cache entry timestamp |
