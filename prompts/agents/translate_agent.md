Agent: Translate Agent v0.1

Goals
- Provide provider-agnostic translation for titles, descriptions, and review texts.
- Preserve original text; store translation, provider metadata, quality/confidence if available, and cost estimates.
- Deduplicate by content hash; chunk long bodies; respect token/char budgets.

Inputs (JSON)
{
  "target_lang": "en",
  "batch_size": 100,
  "max_chars_per_call": 8000,
  "providers_priority": ["deepl", "llm"],  // try in order; fall back if unavailable
  "dry_run": false
}

Allowed files to create/modify
- apps/core/translate.py (new): provider interfaces + batching/chunking/caching.
- apps/core/utils/text.py: language detection hook, hashing, chunkers.
- apps/core/models.py: app_locales.desc_en/title_en fields; reviews.body_en/title_en; translation_provider; translated_at.
- prompts/io_schemas.md: append TranslationRecord schema.
- docs/data_model.md: update translation-related fields.

Tools
- DB session access; select rows where translated fields are null and locale != 'en'.
- Provider wrappers:
  - DeepLProvider (env: DEEPL_API_KEY) [stub OK].
  - LLMProvider (env: OPENAI_API_KEY or other) [stub OK].
  - NullProvider for tests (echo).

Constraints
- Never overwrite existing translations unless force=true is provided.
- Keep paragraph boundaries; chunk by sentence where possible.
- Cache by SHA256(original_text + source_lang + target_lang + provider_name).
- Record per-call estimated cost (tokens or chars) to a simple ledger.

Deliverables
- PR diff with apps/core/translate.py including:
  - Base class TranslationProvider with translate_texts(list[str], src_lang|None, tgt_lang) -> list[TranslatedItem].
  - Implement DeepLProvider (real call or clear TODO with interfaces), LLMProvider (prompt template), NullProvider.
  - translate_records(session, table, text_fields=[...], src_lang_field, src_locale_field, tgt_lang="en").
- Schema updates in models.py and migration notes (if fields missing).
- Minimal CLI hook (optional) or function callable from apps/ingest/cli.py enrich --translate.

High-level implementation plan
1) Utils
   - text.hash_text(s: str) -> hex; text.detect_lang(s: str) -> lang (fastText/langdetect).
   - text.chunk_text(s: str, max_chars) -> list[str] (respect sentence ends).

2) Providers
   - DeepLProvider: map lang codes; batch by max_chars_per_call; collect costs.
   - LLMProvider: system prompt = "You are a precise translator..."; user prompt includes source lang and preserve app-store style; no hallucinations.
   - NullProvider: returns original text with "[NULL_PROVIDER]" tag.

3) Orchestration
   - Query untranslated rows in app_locales and reviews where locale != 'en'.
   - Dedup by hash; translate in batches; write back translations with provider and translated_at.
   - Update evidence bundles with translation provenance.

Output format
- PR diff plus JSON run report:
  { "tasks": ["utils","providers","orchestrator"], "files_changed": [...], "translated_count": N, "dedup_hits": M, "est_cost": {"deepl_chars": X, "llm_tokens": Y} }

Self-checklist
- [ ] Original text always preserved.
- [ ] Translations stored with provider + timestamp.
- [ ] Hash-based cache works; repeated runs skip unchanged content.
- [ ] Chunking respects sentence boundaries.
- [ ] Dry run prints counts only.

Don't do
- Don't summarize or rewrite beyond faithful translation.
- Don't translate code snippets or URLs inside descriptions (leave verbatim).
