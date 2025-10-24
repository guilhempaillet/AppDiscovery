# IO Schemas (v0.1)

## Candidate (ingest output → DB)
- store: str ("apple" | "google_play")
- store_app_id: str
- bundle_or_package_id: str | null
- title_raw: str
- desc_raw: str
- locale: str (BCP-47)
- developer: str
- category: str | null
- price: float | null
- currency: str | null
- countries: list[str] | null
- first_seen_at: datetime
- last_seen_at: datetime

## Evidence
- app_id: int
- source_urls: list[str]
- fetched_at: datetime
- cached_paths: list[str]
- review_samples: list[{rating:int, created_at:datetime, body_raw:str, locale:str}]
- lang_detect: {detected:str, confidence:float}

## TranslationRecord
- table: str ("app_locales" | "reviews")
- record_id: int
- field: str ("title" | "desc" | "body" | "title_review")
- src_locale: str
- tgt_lang: str ("en")
- provider: str ("deepl" | "llm" | "null")
- cost_estimate: {chars:int | null, tokens:int | null}
- translated_at: datetime

## SignalsRecord (per app per date)
- app_id: int
- date: date
- review_7d: int | null
- review_30d: int | null
- rating_velocity_d1: int | null
- text_density: int | null
- window_used: {"7d"|"14d"} | {"30d"|"60d"} | null
