"""SQLite persistence, warehouse loading, and backwards-compatible queries."""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from config import DATABASE_PATH

@contextmanager
def get_connection(db_path=None):
    path = Path(db_path or DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_database(db_path=None):
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        conn.executescript(schema)
        _migrate_columns(conn, "posts", {
            "engagement_total":"INTEGER NOT NULL DEFAULT 0", "hashtag_count":"INTEGER NOT NULL DEFAULT 0",
            "text_length":"INTEGER NOT NULL DEFAULT 0", "word_count":"INTEGER NOT NULL DEFAULT 0",
            "post_date":"TEXT NOT NULL DEFAULT ''", "post_hour":"INTEGER NOT NULL DEFAULT 0",
            "day_of_week":"TEXT NOT NULL DEFAULT ''", "polarity":"REAL NOT NULL DEFAULT 0"})
        _migrate_columns(conn, "pipeline_runs", {
            "source":"TEXT NOT NULL DEFAULT 'csv'", "total_input":"INTEGER NOT NULL DEFAULT 0",
            "new_records":"INTEGER NOT NULL DEFAULT 0", "duplicate_records":"INTEGER NOT NULL DEFAULT 0",
            "processed_records":"INTEGER NOT NULL DEFAULT 0", "failed_records":"INTEGER NOT NULL DEFAULT 0",
            "quality_status":"TEXT NOT NULL DEFAULT 'PASS'", "error_message":"TEXT",
            "execution_seconds":"REAL NOT NULL DEFAULT 0", "missing_values":"INTEGER NOT NULL DEFAULT 0",
            "invalid_records":"INTEGER NOT NULL DEFAULT 0", "invalid_platforms":"INTEGER NOT NULL DEFAULT 0",
            "invalid_engagement_values":"INTEGER NOT NULL DEFAULT 0", "quality_percentage":"REAL NOT NULL DEFAULT 100",
            "invalid_sentiments":"INTEGER NOT NULL DEFAULT 0", "missing_value_records":"INTEGER NOT NULL DEFAULT 0",
            "quality_duplicate_records":"INTEGER NOT NULL DEFAULT 0", "valid_records":"INTEGER NOT NULL DEFAULT 0",
            "missing_by_column_json":"TEXT NOT NULL DEFAULT '{}'"})
        version = conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
        if version < 3:
            _backfill_post_columns(conn)
            _backfill_warehouse(conn)
            conn.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(3,?)", (datetime.now(timezone.utc).isoformat(),))

def _migrate_columns(conn, table, columns):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def _backfill_post_columns(conn):
    """Fill derived fields added after the original Task 1 database was created."""
    rows = conn.execute("SELECT post_id,created_at,likes,comments,shares,hashtags,text,date,day,sentiment_score FROM posts").fetchall()
    for row in rows:
        item = dict(row)
        created = pd.to_datetime(item["created_at"], errors="coerce", utc=True)
        date_value = item.get("date") or ""
        parsed_date = pd.to_datetime(date_value, errors="coerce")
        post_date = parsed_date.strftime("%Y-%m-%d") if pd.notna(parsed_date) else ""
        hashtags = str(item.get("hashtags") or "").split()
        text = str(item.get("text") or "")
        conn.execute("""UPDATE posts SET engagement_total=?,post_date=?,post_hour=?,day_of_week=?,polarity=?,hashtag_count=?,text_length=?,word_count=? WHERE post_id=?""", (
            int(item["likes"] or 0) + int(item["comments"] or 0) + int(item["shares"] or 0),
            post_date, int(created.hour) if pd.notna(created) else 0,
            created.strftime("%A") if pd.notna(created) else (item.get("day") or "Unknown"),
            float(item.get("sentiment_score") or 0), sum(tag.startswith("#") for tag in hashtags),
            len(text), len(text.split()), item["post_id"]))

def _backfill_warehouse(conn):
    """Populate or synchronize analytical facts from an existing operational table."""
    for row in conn.execute("SELECT * FROM posts").fetchall():
        item = dict(row)
        day = item.get("post_date") or item.get("date") or "1970-01-01"
        parsed = pd.to_datetime(day, errors="coerce")
        date_id = parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else "1970-01-01"
        conn.execute("INSERT OR IGNORE INTO dim_platform(platform_name) VALUES(?)", (item["platform"],))
        conn.execute("INSERT OR IGNORE INTO dim_date(date_id,year,month,day,day_of_week) VALUES(?,?,?,?,?)", (date_id, parsed.year if pd.notna(parsed) else 1970, parsed.month if pd.notna(parsed) else 1, parsed.day if pd.notna(parsed) else 1, item.get("day_of_week") or item.get("day") or "Unknown"))
        platform_id = conn.execute("SELECT platform_id FROM dim_platform WHERE platform_name=?", (item["platform"],)).fetchone()[0]
        conn.execute("""INSERT INTO fact_social_posts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(post_id) DO UPDATE SET platform_id=excluded.platform_id,date_id=excluded.date_id,
            likes=excluded.likes,comments=excluded.comments,shares=excluded.shares,
            engagement_total=excluded.engagement_total,engagement_rate=excluded.engagement_rate,
            sentiment=excluded.sentiment,polarity=excluded.polarity,subjectivity=excluded.subjectivity,
            hashtag_count=excluded.hashtag_count,text_length=excluded.text_length,word_count=excluded.word_count""", (item["post_id"], platform_id, date_id, item["likes"], item["comments"], item["shares"], item["engagement_total"], item["engagement_rate"], item["sentiment"], item["polarity"], item["subjectivity"], item.get("hashtag_count",0), item.get("text_length",0), item.get("word_count",0)))
        for hashtag in set(str(item.get("hashtags", "")).split()):
            if hashtag.startswith("#"):
                conn.execute("INSERT OR IGNORE INTO post_hashtags(post_id,hashtag) VALUES(?,?)", (item["post_id"], hashtag.lower()))

def database_initialized(db_path=None):
    path = Path(db_path or DATABASE_PATH)
    if not path.exists(): return False
    with get_connection(path) as conn:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='posts'").fetchone() is not None

POST_COLUMNS = ["post_id", "platform", "username", "text", "created_at", "likes", "comments", "shares", "hashtags", "engagement", "engagement_rate", "sentiment", "sentiment_score", "subjectivity", "date", "month", "day", "engagement_total", "hashtag_count", "text_length", "word_count", "post_date", "post_hour", "day_of_week", "polarity"]

def existing_post_ids(db_path=None):
    with get_connection(db_path) as conn:
        return {row[0] for row in conn.execute("SELECT post_id FROM posts")}

def insert_posts(frame, db_path=None):
    """Insert operational posts and update warehouse dimensions/facts."""
    if frame.empty: return 0
    data = frame.copy()
    for target, source in (("engagement_total", "engagement"), ("post_date", "date"), ("day_of_week", "day"), ("polarity", "sentiment_score")):
        if target not in data: data[target] = data[source] if source in data else 0
    for col in POST_COLUMNS:
        if col not in data: data[col] = 0 if col in {"likes", "comments", "shares", "engagement", "engagement_rate", "sentiment_score", "subjectivity", "hashtag_count", "text_length", "word_count", "post_hour", "polarity", "engagement_total"} else ""
    values = [tuple(row) for row in data[POST_COLUMNS].itertuples(index=False, name=None)]
    sql = f"INSERT OR IGNORE INTO posts ({','.join(POST_COLUMNS)}) VALUES ({','.join('?' for _ in POST_COLUMNS)})"
    inserted = 0
    with get_connection(db_path) as conn:
        for row, value in zip(data.to_dict("records"), values):
            cur = conn.execute(sql, value)
            if not cur.rowcount: continue
            inserted += 1
            platform = row["platform"]
            day_value = str(row.get("post_date") or row.get("date") or "")
            date = pd.to_datetime(day_value, errors="coerce")
            date_id = date.strftime("%Y-%m-%d") if pd.notna(date) else "1970-01-01"
            conn.execute("INSERT OR IGNORE INTO dim_platform(platform_name) VALUES(?)", (platform,))
            conn.execute("INSERT OR IGNORE INTO dim_date(date_id,year,month,day,day_of_week) VALUES(?,?,?,?,?)", (date_id, date.year if pd.notna(date) else 1970, date.month if pd.notna(date) else 1, date.day if pd.notna(date) else 1, str(row.get("day_of_week") or row.get("day") or "Unknown")))
            platform_id = conn.execute("SELECT platform_id FROM dim_platform WHERE platform_name=?", (platform,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO fact_social_posts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                row["post_id"], platform_id, date_id, int(row.get("likes",0)), int(row.get("comments",0)), int(row.get("shares",0)),
                int(row.get("engagement_total",row.get("engagement",0))), float(row.get("engagement_rate",0)), row.get("sentiment","Neutral"),
                float(row.get("polarity",row.get("sentiment_score",0))), float(row.get("subjectivity",0)), int(row.get("hashtag_count",0)),
                int(row.get("text_length",0)), int(row.get("word_count",0))))
            for hashtag in set(str(row.get("hashtags","")).split()):
                if hashtag.startswith("#"):
                    conn.execute("INSERT OR IGNORE INTO post_hashtags(post_id,hashtag) VALUES(?,?)", (row["post_id"], hashtag.lower()))
    return inserted

def insert_pipeline_run(run, db_path=None):
    with get_connection(db_path) as conn:
        fields = ("started_at","completed_at","records_loaded","records_processed","records_failed","status","source","total_input","new_records","duplicate_records","processed_records","failed_records","quality_status","error_message","execution_seconds","missing_values","invalid_records","invalid_platforms","invalid_engagement_values","quality_percentage","invalid_sentiments","missing_value_records","quality_duplicate_records","valid_records")
        values = [run.get(field, 0) for field in fields]
        values.append(json.dumps(run.get("missing_by_column", {}), sort_keys=True))
        cur = conn.execute("""INSERT INTO pipeline_runs(started_at,completed_at,records_loaded,records_processed,records_failed,status,source,total_input,new_records,duplicate_records,processed_records,failed_records,quality_status,error_message,execution_seconds,missing_values,invalid_records,invalid_platforms,invalid_engagement_values,quality_percentage,invalid_sentiments,missing_value_records,quality_duplicate_records,valid_records,missing_by_column_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
        return cur.lastrowid

def fetch_posts(db_path=None, limit=500):
    with get_connection(db_path) as conn: return pd.read_sql_query("SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", conn, params=(limit,))

def _rows(sql, params=(), db_path=None):
    with get_connection(db_path) as conn: return [dict(r) for r in conn.execute(sql, params).fetchall()]

def fetch_summary(db_path=None):
    rows = _rows("SELECT COUNT(*) total_posts, COALESCE(AVG(engagement),0) average_engagement, (SELECT platform FROM posts GROUP BY platform ORDER BY COUNT(*) DESC LIMIT 1) top_platform, COALESCE(SUM(sentiment='Positive'),0) positive_posts, COALESCE(SUM(sentiment='Negative'),0) negative_posts, COALESCE(SUM(sentiment='Neutral'),0) neutral_posts FROM posts", db_path=db_path)
    return rows[0]

def fetch_sentiment_summary(db_path=None): return _rows("SELECT sentiment, COUNT(*) count FROM posts GROUP BY sentiment ORDER BY sentiment", db_path=db_path)
def fetch_platform_summary(db_path=None): return _rows("SELECT platform, COUNT(*) posts, ROUND(AVG(engagement_total),2) average_engagement FROM posts GROUP BY platform ORDER BY posts DESC", db_path=db_path)
def fetch_daily_sentiment_trend(db_path=None): return _rows("SELECT post_date date, sentiment, COUNT(*) count FROM posts GROUP BY post_date,sentiment ORDER BY post_date", db_path=db_path)
def fetch_top_hashtags(db_path=None, limit=10): return _rows("SELECT hashtag,COUNT(*) count FROM post_hashtags GROUP BY hashtag ORDER BY count DESC,hashtag LIMIT ?", (int(limit),), db_path)
def fetch_engagement_statistics(db_path=None): return _rows("SELECT platform,ROUND(AVG(likes),2) average_likes,ROUND(AVG(comments),2) average_comments,ROUND(AVG(shares),2) average_shares,ROUND(AVG(engagement_total),2) average_engagement FROM posts GROUP BY platform ORDER BY average_engagement DESC", db_path=db_path)
