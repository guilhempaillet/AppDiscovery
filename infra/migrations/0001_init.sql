-- Initial schema for AppDiscovery
-- SQLite-compatible SQL (adjust for PostgreSQL in production)

-- Stores table
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_stores_name ON stores(name);

-- Apps table
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    store_app_id TEXT NOT NULL,
    bundle_or_package_id TEXT,
    developer TEXT,
    category TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT uq_app_store_id UNIQUE (store_id, store_app_id)
);

CREATE INDEX IF NOT EXISTS ix_apps_store_id ON apps(store_id);
CREATE INDEX IF NOT EXISTS ix_apps_store_app_id ON apps(store_app_id);
CREATE INDEX IF NOT EXISTS ix_app_bundle_id ON apps(bundle_or_package_id);

-- App locales table
CREATE TABLE IF NOT EXISTS app_locales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    locale TEXT NOT NULL,
    title_raw TEXT NOT NULL,
    desc_raw TEXT,
    title_en TEXT,
    desc_en TEXT,
    translation_provider TEXT,
    translated_at TIMESTAMP,
    price REAL,
    currency TEXT,
    countries TEXT,  -- JSON array
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(id),
    CONSTRAINT uq_app_locale UNIQUE (app_id, locale)
);

CREATE INDEX IF NOT EXISTS ix_app_locales_app_id ON app_locales(app_id);
CREATE INDEX IF NOT EXISTS ix_app_locale_locale ON app_locales(locale);

-- Reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    store_review_id TEXT NOT NULL,
    locale TEXT NOT NULL,
    rating INTEGER NOT NULL,
    title_raw TEXT,
    body_raw TEXT,
    title_en TEXT,
    body_en TEXT,
    translation_provider TEXT,
    translated_at TIMESTAMP,
    author_name TEXT,
    created_at TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(id),
    CONSTRAINT uq_review_store_id UNIQUE (app_id, store_review_id)
);

CREATE INDEX IF NOT EXISTS ix_reviews_app_id ON reviews(app_id);
CREATE INDEX IF NOT EXISTS ix_review_created_at ON reviews(created_at);
CREATE INDEX IF NOT EXISTS ix_review_locale ON reviews(locale);

-- Daily snapshots table
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    date DATE NOT NULL,
    rating_total INTEGER,
    rating_count INTEGER,
    rating_avg REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(id),
    CONSTRAINT uq_snapshot_app_date UNIQUE (app_id, date)
);

CREATE INDEX IF NOT EXISTS ix_daily_snapshots_app_id ON daily_snapshots(app_id);
CREATE INDEX IF NOT EXISTS ix_snapshot_date ON daily_snapshots(date);

-- Evidence table
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    source_urls TEXT NOT NULL,  -- JSON array
    cached_paths TEXT,  -- JSON array
    review_samples TEXT,  -- JSON array
    lang_detect TEXT,  -- JSON object
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(id)
);

CREATE INDEX IF NOT EXISTS ix_evidence_app_id ON evidence(app_id);
CREATE INDEX IF NOT EXISTS ix_evidence_fetched_at ON evidence(fetched_at);

-- Insert default stores
INSERT OR IGNORE INTO stores (name, display_name, enabled) VALUES
    ('apple', 'Apple App Store', TRUE),
    ('google_play', 'Google Play Store', FALSE);
