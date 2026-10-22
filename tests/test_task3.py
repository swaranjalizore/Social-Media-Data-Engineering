import pandas as pd
import pytest
import sqlite3

from analytics.queries import (
    fetch_advanced_kpis, fetch_dashboard_analytics, fetch_filtered_platform_analytics,
    fetch_filtered_sentiment_distribution, fetch_hashtag_engagement,
    fetch_posts_by_hour, fetch_posts_by_weekday, fetch_recent_pipeline_runs,
)
from app import create_app
from config import PROCESSED_DATA_DIR
from database.db import initialize_database, insert_posts, get_connection
from pipeline.transformation import transform_posts
from pipeline.validation import quality_report

def prepared_database(path):
    initialize_database(path)
    frame = pd.DataFrame([
        {"post_id":"a1","platform":"Instagram","username":"maker_a","text":"A delightful launch #daily #design","created_at":"2025-08-01T09:00:00Z","likes":10,"comments":2,"shares":1,"hashtags":"#daily #design","sentiment":"Positive","sentiment_score":0.7,"subjectivity":0.8},
        {"post_id":"b1","platform":"X","username":"maker_b","text":"The update is frustrating #daily","created_at":"2025-08-02T17:00:00Z","likes":5,"comments":4,"shares":2,"hashtags":"#daily","sentiment":"Negative","sentiment_score":-0.6,"subjectivity":0.7},
        {"post_id":"a2","platform":"Instagram","username":"maker_c","text":"The event begins at noon #event","created_at":"2025-08-03T12:00:00Z","likes":7,"comments":1,"shares":0,"hashtags":"#event","sentiment":"Neutral","sentiment_score":0.0,"subjectivity":0.2},
    ])
    # Keep the test fixture's supplied sentiment labels while using the real transform fields.
    labels = frame["sentiment"].copy()
    scores = frame["sentiment_score"].copy()
    transformed = transform_posts(frame)
    transformed["sentiment"] = labels
    transformed["sentiment_score"] = scores
    transformed["polarity"] = scores
    insert_posts(transformed, path)

def test_advanced_analytics_and_dashboard_payload(tmp_path):
    db=tmp_path/"analytics.db"; prepared_database(db)
    kpis=fetch_advanced_kpis(db_path=db)
    assert kpis["total_posts"]==3 and kpis["total_platforms"]==2
    assert kpis["total_engagement"]==32 and kpis["total_hashtags"]==3
    assert kpis["positive_posts"]==1 and kpis["negative_posts"]==1 and kpis["neutral_posts"]==1
    # Independently rounded percentages may differ from 100 by one hundredth.
    assert abs(sum(x["percentage"] for x in fetch_filtered_sentiment_distribution(db_path=db))-100)<=0.02
    platform=fetch_filtered_platform_analytics(db_path=db)
    assert platform[0]["platform"]=="Instagram" and platform[0]["positive_posts"]==1
    assert len(fetch_posts_by_hour(db_path=db))==3 and len(fetch_posts_by_weekday(db_path=db))==3
    hashtag=fetch_hashtag_engagement(db_path=db)
    daily=next(item for item in hashtag if item["hashtag"]=="#daily")
    assert daily["usage_count"]==2 and daily["average_engagement"]==12.0
    payload=fetch_dashboard_analytics({"platform":"Instagram"},db)
    assert payload["kpis"]["total_posts"]==2 and payload["filters"]["platform"]=="Instagram"

def test_quality_report_percentage_and_invalid_sentiment():
    frame=pd.DataFrame([{"post_id":"ok","platform":"X","username":"u","text":"hi","created_at":"2025-01-01","likes":1,"comments":0,"shares":0,"hashtags":"","sentiment":"Mystery"}])
    report=quality_report(frame)
    assert report["invalid_sentiments"]==1 and report["quality_percentage"]==0
    assert "hashtags" in report["missing_by_column"]

def test_filtered_api_parameters_and_health(tmp_path):
    db=tmp_path/"api.db"; prepared_database(db)
    client=create_app({"TESTING":True,"DATABASE_PATH":db}).test_client()
    assert client.get("/api/health").get_json()["status"]=="ok"
    response=client.get("/api/analytics/dashboard?platform=Instagram&start_date=2025-08-01&end_date=2025-08-03")
    assert response.status_code==200 and response.get_json()["data"]["kpis"]["total_posts"]==2
    assert client.get("/api/analytics/dashboard?platform=Unknown").status_code==400
    assert client.get("/api/analytics/dashboard?start_date=2025-99-99").status_code==400
    assert client.get("/api/analytics/dashboard?start_date=2025-08-03&end_date=2025-08-01").status_code==400
    assert client.get("/api/top-posts?limit=999").status_code==400
    malformed=client.post("/api/pipeline/run",data="{broken",content_type="application/json")
    assert malformed.status_code==400 and malformed.is_json
    missing_route=client.get("/api/does-not-exist")
    assert missing_route.status_code==404 and missing_route.is_json
    export=client.get("/api/export?platform=X")
    assert export.status_code==200 and b"b1" in export.data and b"a1" not in export.data
    empty_export=client.get("/api/export?platform=Facebook")
    assert empty_export.status_code==200 and b"post_id" in empty_export.data

def test_failed_pipeline_attempt_is_audited(tmp_path):
    db=tmp_path/"failed-run.db"
    with pytest.raises(FileNotFoundError):
        from pipeline.pipeline import run_pipeline
        run_pipeline(csv_path=tmp_path/"missing.csv",db_path=db,save_processed=False)
    runs=fetch_recent_pipeline_runs(db)
    assert len(runs)==1 and runs[0]["status"]=="failed"
    with get_connection(db) as conn:
        error=conn.execute("SELECT error_message FROM pipeline_runs").fetchone()[0]
    assert "not found" in error.lower()

def test_pipeline_api_hides_internal_failure_and_records_run(tmp_path):
    db=tmp_path/"api-failed.db"
    client=create_app({"TESTING":True,"DATABASE_PATH":db,"RAW_DATA_PATH":tmp_path/"absent.csv"}).test_client()
    response=client.post("/api/pipeline/run",json={})
    assert response.status_code==500
    assert response.get_json()["error"]=="Pipeline could not be completed. Check the application log."
    assert str(tmp_path) not in response.get_data(as_text=True)
    assert client.get("/api/pipeline/runs").get_json()[0]["status"]=="failed"

def test_legacy_task1_database_migration_backfills_derived_fields(tmp_path):
    db=tmp_path/"legacy.db"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE posts(post_id TEXT PRIMARY KEY,platform TEXT,username TEXT,text TEXT,created_at TEXT,likes INTEGER,comments INTEGER,shares INTEGER,hashtags TEXT,engagement INTEGER,engagement_rate REAL,sentiment TEXT,sentiment_score REAL,subjectivity REAL,date TEXT,month TEXT,day TEXT);
            CREATE TABLE pipeline_runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT,completed_at TEXT,records_loaded INTEGER,records_processed INTEGER,records_failed INTEGER,status TEXT);
            INSERT INTO posts VALUES('legacy1','Instagram','learner','Great local release #data','2025-07-02T14:25:00Z',10,3,2,'#data',15,0.75,'Positive',0.6,0.8,'2025-07-02','2025-07','Wednesday');
        """)
    initialize_database(db)
    with get_connection(db) as conn:
        post=conn.execute("SELECT engagement_total,post_date,post_hour,day_of_week,polarity,hashtag_count,text_length,word_count FROM posts WHERE post_id='legacy1'").fetchone()
        assert tuple(post)==(15,'2025-07-02',14,'Wednesday',0.6,1,25,4)
        assert conn.execute("SELECT COUNT(*) FROM fact_social_posts").fetchone()[0]==1
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]==3
    initialize_database(db)
    with get_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM fact_social_posts").fetchone()[0]==1

def test_custom_database_exports_stay_beside_custom_database(tmp_path):
    from pipeline.pipeline import run_pipeline
    source=tmp_path/"one.csv"
    pd.DataFrame([{"post_id":"export1","platform":"X","username":"maker","text":"Good update #one","created_at":"2025-01-01T01:00:00Z","likes":3,"comments":1,"shares":0,"hashtags":"#one"}]).to_csv(source,index=False)
    run_pipeline(csv_path=source,db_path=tmp_path/"isolated.db")
    local_output=tmp_path/"processed"/"social_media_posts_processed.csv"
    assert local_output.exists() and len(pd.read_csv(local_output))==1
    assert local_output.resolve().parent != PROCESSED_DATA_DIR.resolve()
