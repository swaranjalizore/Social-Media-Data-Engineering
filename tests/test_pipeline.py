import pandas as pd
from pipeline.ingestion import load_posts
from pipeline.cleaning import clean_posts
from pipeline.validation import validate_posts
from pipeline.transformation import transform_posts

def test_csv_ingestion(tmp_path):
    path=tmp_path/'posts.csv'; pd.DataFrame([{"post_id":"a","text":"hello"}]).to_csv(path,index=False)
    assert len(load_posts(path))==1

def test_duplicate_removal():
    frame=pd.DataFrame([{"post_id":"a","platform":"X","username":"@A","text":" hi   there ","created_at":"2025-01-01","likes":2,"comments":0,"shares":1,"hashtags":"##AI"}]*2)
    cleaned=clean_posts(frame)
    assert len(cleaned)==1 and cleaned.iloc[0].text=='hi there' and cleaned.iloc[0].hashtags=='#ai'

def test_validation_counts_invalid_rows():
    frame=pd.DataFrame([{"post_id":"","platform":"Bad","username":"u","text":"","created_at":"no-date","likes":-1,"comments":0,"shares":0,"hashtags":""}])
    result=validate_posts(frame)
    assert result['total_records']==1 and result['valid_records']==0 and result['invalid_records']==1

def test_transformation_metrics():
    frame=pd.DataFrame([{"likes":4,"comments":2,"shares":1,"created_at":"2025-06-03T12:00:00Z"}])
    result=transform_posts(frame).iloc[0]
    assert result.engagement==7 and result.date=='2025-06-03' and result.month=='2025-06'
