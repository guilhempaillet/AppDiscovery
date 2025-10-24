# North Star

## Vision

Build a **multi-agent app intelligence platform** that helps researchers, developers, and analysts understand mobile app ecosystems through evidence-based insights.

## Goals

### Week 1 (MVP) ✅
- ✅ **Ingest Agent**: Search and fetch Apple App Store metadata + reviews
- ✅ **Cache layer**: SHA256-based HTTP caching with rate limiting
- ✅ **Database**: SQLModel schema for apps, locales, reviews, snapshots
- ✅ **CLI**: `discover` and `enrich` commands with idempotent upserts
- ✅ **Evidence bundles**: JSON artifacts linking apps to source URLs
- ✅ **Tests**: Smoke tests for Apple API integration

### Week 2
- 📋 **Translate Agent**: Provider-agnostic translation (DeepL, OpenAI)
  - Hash-based deduplication
  - Chunking for long descriptions
  - Cost tracking per provider
- 📋 **Signals Agent**: Compute traction metrics
  - review_7d, review_30d (rolling windows)
  - rating_velocity_d1 (day-over-day changes)
  - text_density (description length)

### Week 3
- 🔜 **Google Play support** (gated by compliance_ok)
- 🔜 **REST API** for external integrations
- 🔜 **Background worker** for scheduled ingests

### Week 4+
- 🔜 **Reviewer Copilot**: LLM-assisted analysis from evidence
- 🔜 **Docs Agent**: Auto-update documentation
- 🔜 **Embeddings + semantic search**
- 🔜 **Dashboard UI** for exploration

## Success Metrics

### Technical
- **Cache hit rate** >80% for repeated queries
- **API success rate** >95% with retries
- **Idempotency**: Re-running commands produces identical DB state

### User Value
- Discover **100+ apps** per query in <10 seconds
- Enrich **full details + reviews** for 10 apps in <60 seconds
- **Multi-language support** with automatic translation
- **Evidence-backed** analysis (no hallucinations)

## Constraints

### Must Have
- ✅ Respect store TOS (official APIs only)
- ✅ Cache all HTTP calls
- ✅ Idempotent operations
- ✅ No PII beyond public data
- ✅ Structured logging for observability

### Must Not Have
- ❌ Credential harvesting or bulk SSH key scraping
- ❌ Malicious use cases (defensive security only)
- ❌ Invented data (evidence over opinion)
- ❌ Secrets in code

## Architecture Philosophy

### Multi-Agent Design

Each agent is a **specialized autonomous unit** with:
- Clear **role and responsibilities**
- Defined **allowed files** (see `prompts/agents.md`)
- Specific **tools and constraints**
- Independent **test suite**

Agents communicate via:
- **Database** (shared schema)
- **Evidence bundles** (JSON artifacts)
- **Orchestrator** (for sequencing, not implemented yet)

### Retrieval-First

LLMs reason over evidence, not open web:
1. **Fetch** data via official APIs
2. **Cache** responses with content hash
3. **Persist** to structured database
4. **Bundle** evidence with source URLs
5. **Reason** over cached/persisted facts

### Composable Workflows

Users can:
- Run agents **individually** (`discover`, `enrich`, `translate`)
- **Chain** agents via CLI (`enrich --translate --compute-signals`)
- **Schedule** agents for daily updates (future)
- **Extend** with new agents following the same patterns

## What We're Building

Not just another web scraper. AppDiscovery is:
- A **research platform** for understanding app ecosystems
- An **evidence engine** that tracks provenance and sources
- A **multi-agent system** with clear separation of concerns
- A **foundation** for LLM-assisted app analysis

### Use Cases

1. **Market Research**: Discover trending apps in specific locales/categories
2. **Competitive Analysis**: Track rating velocity and review sentiment
3. **Localization**: Analyze app descriptions across languages
4. **Academic Research**: Study app store dynamics with citation-quality evidence
5. **Developer Tools**: Monitor competitor features and user feedback

## Non-Goals

- Not a complete app store (no downloads or purchases)
- Not real-time monitoring (daily/weekly updates are fine)
- Not a sentiment analysis tool (though can support it)
- Not a scraping service (official APIs only, compliance-first)

---

**Next Milestone**: Week 2 - Translation and Signals agents
