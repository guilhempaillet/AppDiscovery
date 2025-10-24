Agent: Signals Agent v0.1

Goals
- Compute Week 1 basic traction signals and persist daily:
  - review_7d, review_30d
  - rating_velocity_d1 (starting on day 2 of snapshots)
  - text_density (chars_in_desc_raw)
- Backfill once for existing apps; schedule a daily run at 02:00 UTC (cron outside scope here).

Inputs (JSON)
{
  "since": "2025-10-27",
  "recompute_text_density": true,
  "dry_run": false
}

Allowed files to create/modify
- apps/core/signals.py (new): computations and DB writes.
- apps/core/models.py: signals table (id, app_id, date, review_7d, review_30d, rating_velocity_d1, text_density).
- apps/core/db.py: helper for date-bounded queries.
- infra/migrations/*: add signals table if missing.
- prompts/io_schemas.md: append SignalsRecord schema.
- docs/data_model.md: update definitions.

Constraints
- Null-safe math: if yesterday's snapshot missing, set rating_velocity_d1 = null.
- Windowed counts based on reviews.created_at; if sparse, allow fallback to 14d/60d but record which window used.
- Do not infer install counts or sentiment in Week 1.

Deliverables
- PR diff with:
  - signals.py functions:
    - compute_review_windows(session, app_id, as_of_date)
    - compute_rating_velocity(session, app_id, as_of_date)
    - compute_text_density(session, app_id)
    - upsert_signals(session, app_id, date, values)
  - Tests: basic unit tests for window math with synthetic data.
  - CLI hook via apps/ingest/cli.py enrich --compute-signals (optional).

Reference SQL skeleton (for window counts; adapt to ORM)
- review_7d:
  SELECT COUNT(*) FROM reviews r WHERE r.app_id=:app_id AND r.created_at > (:as_of_date - INTERVAL '7 days');
- review_30d:
  SELECT COUNT(*) FROM reviews r WHERE r.app_id=:app_id AND r.created_at > (:as_of_date - INTERVAL '30 days');
- rating_velocity_d1:
  SELECT s2.rating_total - s1.rating_total
  FROM daily_snapshots s1
  JOIN daily_snapshots s2 ON s1.app_id=s2.app_id
  WHERE s2.date=:as_of_date AND s1.date=(:as_of_date - INTERVAL '1 day') AND s1.app_id=:app_id;

Output format
- PR diff plus JSON run report:
  { "tasks": ["windows","velocity","density"], "files_changed": [...], "apps_processed": N, "dry_run": false }

Self-checklist
- [ ] No exceptions if a window has no data; store zeros with window_used field or set to null per spec.
- [ ] Velocity only when two consecutive snapshots exist.
- [ ] Text density computed from app_locales.desc_raw length for primary non-EN listing.
- [ ] Tests cover empty, sparse, and dense cases.

Don't do
- Don't compute sentiment or embeddings.
- Don't backfill missing snapshots; that's the ingest/scheduler's job.
