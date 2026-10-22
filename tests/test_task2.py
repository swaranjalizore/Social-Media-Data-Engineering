import json
import pandas as pd
from analytics.queries import fetch_recent_pipeline_runs
from database.db import get_connection, initialize_database
from pipeline.pipeline import run_pipeline
from pipeline.source import JSON_DATA_PATH, load_source
from pipeline.transformation import transform_posts
from pipeline.validation import quality_report

def sample_row(post_id="batch_1"):
    return {"post_id":post_id,"platform":"Instagram","username":"person","text":"A useful and delightful update #sample","created_at":"2025-08-01T13:45:00Z","likes":12,"comments":3,"shares":2,"hashtags":"#sample"}

def test_json_source_ingestion():
    frame=load_source("json",JSON_DATA_PATH)
    assert len(frame)>=5 and {"post_id","text","platform"}.issubset(frame.columns)

def test_quality_report_detects_missing_duplicate_platform_and_metrics():
    first=sample_row(); duplicate=sample_row()
    invalid=sample_row("bad"); invalid.update(platform="Threads",username="",text="",created_at="not a date",likes="oops",shares=-1)
    report=quality_report(pd.DataFrame([first,duplicate,invalid]))
    assert report["total_records"]==3 and report["duplicate_records"]==1
    assert report["invalid_platforms"]==1 and report["invalid_engagement_values"]==2
    assert report["missing_values"]>=2 and report["invalid_records"]==2 and report["quality_status"]=="FAIL"

def test_advanced_transform_fields():
    result=transform_posts(pd.DataFrame([sample_row()])).iloc[0]
    assert result.engagement_total==17 and result.hashtag_count==1
    assert result.text_length>0 and result.word_count>0
    assert result.post_date=="2025-08-01" and result.post_hour==13 and result.day_of_week=="Friday"
    assert 0<=result.engagement_rate<=1

def test_incremental_pipeline_and_warehouse_audit(tmp_path):
    source=tmp_path/"batch.json"; source.write_text(json.dumps([sample_row()]),encoding="utf-8")
    db=tmp_path/"warehouse.db"; initialize_database(db)
    first=run_pipeline(db_path=db,source="json",csv_path=source,save_processed=False,batch_size=1)
    second=run_pipeline(db_path=db,source="json",csv_path=source,save_processed=False,batch_size=1)
    assert (first["new_records"],first["processed_records"],first["duplicate_records"])==(1,1,0)
    assert (second["new_records"],second["processed_records"],second["duplicate_records"])==(0,0,1)
    assert first["quality_status"]=="PASS" and second["failed_records"]==0
    with get_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM fact_social_posts").fetchone()[0]==1
        assert conn.execute("SELECT COUNT(*) FROM dim_platform").fetchone()[0]==1
        assert conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]==1
    runs=fetch_recent_pipeline_runs(db)
    assert len(runs)==2 and runs[0]["source"]=="json" and runs[0]["duplicate_records"]==1

def test_invalid_data_quality_metrics(tmp_path):
    source=tmp_path/"bad.csv"
    rows=[sample_row("ok"),sample_row("bad")]; rows[1].update(platform="Unknown",likes=-4)
    pd.DataFrame(rows).to_csv(source,index=False)
    run=run_pipeline(csv_path=source,db_path=tmp_path/"quality.db",save_processed=False)
    assert run["processed_records"]==1 and run["failed_records"]==1
    assert run["quality_status"]=="FAIL" and run["invalid_platforms"]==1
