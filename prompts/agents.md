# Agents registry v0.1 (2025-10-24)

Purpose
- Define clear roles, tools, constraints, and outputs so Claude Code can operate as multiple focused agents within this repo.
- Default operating mode: retrieval-first. LLMs reason only over evidence pulled and cached by our code.

Global policies
- Evidence over opinion. Do not invent data. Never browse the open web directly from an agent unless the task explicitly includes a fetcher and caching layer.
- Respect store TOS. Prefer official/public endpoints. If an endpoint is fragile or unofficial, gate it behind a feature flag and a compliance_ok switch.
- Idempotent by default. All jobs and migrations must be safe to re-run.
- Cost-aware. Track estimated tokens/characters; cache by content hash.
- Observability. Log structured JSON; zero PII beyond review display names.
- Security. No secrets in code. Read from environment or .env.

Shared tools the agents may call
- DB access via apps/core/db.py (SQLAlchemy/SQLModel) and models.py.
- HTTP with caching via apps/ingest/cache.py (respect per-host rate limits/backoff).
- CLI wiring with Typer in each app module (e.g., apps/ingest/cli.py).
- Test runner: pytest.
- LLM/MT providers are abstracted behind provider classes; do not hardcode vendors.

Output formats
- Primary: PR-style diff (unified patch) plus a short summary.
- Secondary: JSON run report {tasks, files_changed, tests_run, est_cost}.

Agent roster
1) Orchestrator (stub; owner: you)
   - Role: translate high-level goals into agent tasks; sequence them; enforce policies.
   - Allowed paths: prompts/agents/*.md only.
   - Output: task plan to other agents.

2) Ingest Agent (implemented)
   - Role: discover, fetch, and persist store metadata/reviews with cache + rate limits.
   - Allowed paths: apps/ingest/**, apps/core/{db.py,models.py}, infra/migrations/*, prompts/io_schemas.md, docs/data_model.md.
   - Never touches: apps/core/utils/text.py, translation providers, scoring logic.

3) Translate Agent (implemented)
   - Role: provider-agnostic translation for titles/descriptions/reviews; store originals + provenance.
   - Allowed paths: apps/core/utils/text.py, apps/core/models.py (translation fields), apps/core/translate.py (new), prompts/io_schemas.md, docs/data_model.md.

4) Signals Agent (implemented)
   - Role: compute Week 1 metrics (review_7d/30d, rating_velocity_d1, text_density) and persist into signals.
   - Allowed paths: apps/core/models.py, apps/core/db.py, apps/core/signals.py (new), infra/migrations/*, prompts/io_schemas.md, docs/data_model.md.

5) Reviewer Copilot (stub)
   - Role: draft 3-bullet rationale strictly from evidence bundles; no new facts.
   - Allowed paths: prompts/agents/reviewer_copilot.md.

6) Docs Agent (stub)
   - Role: update docs/*.md and prompts/io_schemas.md when schemas or flows change.

How to use (vibecoding loop)
- Step 1: Open this file, pick an agent, copy its "Task prompt" skeleton, and provide tight task inputs.
- Step 2: Ask for a PR diff + test plan. Run locally (pytest + CLI).
- Step 3: If schemas or prompts change, ping Docs Agent to update docs and io_schemas.md.

References
- IO schemas: prompts/io_schemas.md
- Data model: docs/data_model.md
- Policies: prompts/policies.md
