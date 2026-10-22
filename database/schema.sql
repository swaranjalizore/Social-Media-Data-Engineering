PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations (
 version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
 post_id TEXT PRIMARY KEY, platform TEXT NOT NULL, username TEXT NOT NULL, text TEXT NOT NULL,
 created_at TEXT NOT NULL, likes INTEGER NOT NULL, comments INTEGER NOT NULL, shares INTEGER NOT NULL,
 hashtags TEXT NOT NULL, engagement INTEGER NOT NULL, engagement_rate REAL NOT NULL,
 sentiment TEXT NOT NULL, sentiment_score REAL NOT NULL, subjectivity REAL NOT NULL,
 date TEXT NOT NULL, month TEXT NOT NULL, day TEXT NOT NULL,
 engagement_total INTEGER NOT NULL DEFAULT 0, hashtag_count INTEGER NOT NULL DEFAULT 0,
 text_length INTEGER NOT NULL DEFAULT 0, word_count INTEGER NOT NULL DEFAULT 0,
 post_date TEXT NOT NULL DEFAULT '', post_hour INTEGER NOT NULL DEFAULT 0,
 day_of_week TEXT NOT NULL DEFAULT '', polarity REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
 run_id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, completed_at TEXT,
 records_loaded INTEGER NOT NULL DEFAULT 0, records_processed INTEGER NOT NULL DEFAULT 0,
 records_failed INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
 source TEXT NOT NULL DEFAULT 'csv', total_input INTEGER NOT NULL DEFAULT 0,
 new_records INTEGER NOT NULL DEFAULT 0, duplicate_records INTEGER NOT NULL DEFAULT 0,
 processed_records INTEGER NOT NULL DEFAULT 0, failed_records INTEGER NOT NULL DEFAULT 0,
 quality_status TEXT NOT NULL DEFAULT 'PASS', error_message TEXT,
 execution_seconds REAL NOT NULL DEFAULT 0, missing_values INTEGER NOT NULL DEFAULT 0,
 invalid_records INTEGER NOT NULL DEFAULT 0, invalid_platforms INTEGER NOT NULL DEFAULT 0,
 invalid_engagement_values INTEGER NOT NULL DEFAULT 0, quality_percentage REAL NOT NULL DEFAULT 100,
 invalid_sentiments INTEGER NOT NULL DEFAULT 0, missing_value_records INTEGER NOT NULL DEFAULT 0,
 quality_duplicate_records INTEGER NOT NULL DEFAULT 0, valid_records INTEGER NOT NULL DEFAULT 0,
 missing_by_column_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS dim_platform (
 platform_id INTEGER PRIMARY KEY AUTOINCREMENT, platform_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS dim_date (
 date_id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL,
 day INTEGER NOT NULL, day_of_week TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_social_posts (
 post_id TEXT PRIMARY KEY REFERENCES posts(post_id) ON DELETE CASCADE,
 platform_id INTEGER NOT NULL REFERENCES dim_platform(platform_id),
 date_id TEXT NOT NULL REFERENCES dim_date(date_id),
 likes INTEGER NOT NULL, comments INTEGER NOT NULL, shares INTEGER NOT NULL,
 engagement_total INTEGER NOT NULL, engagement_rate REAL NOT NULL,
 sentiment TEXT NOT NULL, polarity REAL NOT NULL, subjectivity REAL NOT NULL,
 hashtag_count INTEGER NOT NULL, text_length INTEGER NOT NULL, word_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS post_hashtags (
 post_id TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
 hashtag TEXT NOT NULL, PRIMARY KEY(post_id, hashtag)
);
CREATE INDEX IF NOT EXISTS idx_fact_platform_date ON fact_social_posts(platform_id, date_id);
CREATE INDEX IF NOT EXISTS idx_fact_sentiment ON fact_social_posts(sentiment);
