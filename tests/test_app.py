import pandas as pd
from app import create_app
from database.db import initialize_database, insert_posts
from pipeline.cleaning import clean_posts
from pipeline.transformation import transform_posts
from sentiment.analyzer import analyze_frame

def test_app_health_and_api(tmp_path):
    db=tmp_path/'test.db'; initialize_database(db)
    raw=pd.DataFrame([{"post_id":"x1","platform":"Instagram","username":"u","text":"I love this great day","created_at":"2025-05-01T12:00:00Z","likes":10,"comments":2,"shares":1,"hashtags":"#happy"}])
    insert_posts(analyze_frame(transform_posts(clean_posts(raw))),db)
    app=create_app({"TESTING":True,"DATABASE_PATH":db,"RAW_DATA_PATH":tmp_path/'absent.csv'})
    client=app.test_client()
    assert client.get('/').status_code==200
    assert client.get('/dashboard').status_code==200
    data=client.get('/api/summary').get_json()
    assert data['total_posts']==1 and 'average_engagement' in data
    assert isinstance(client.get('/api/sentiment').get_json(),list)
    assert client.get('/api/platforms').is_json
    assert client.get('/api/trends').is_json
    assert client.get('/api/hashtags').get_json()[0]['hashtag']=='#happy'
    assert client.get('/api/engagement').is_json
    for path in ['/api/quality','/api/pipeline/runs','/api/top-posts','/api/sentiment/platforms','/api/volume/daily','/api/engagement/daily','/api/platform-performance']:
        assert client.get(path).is_json
    export=client.get('/api/export')
    assert export.status_code==200 and export.mimetype=='text/csv'
    assert 'attachment' in export.headers['Content-Disposition']

def test_pipeline_api_returns_run_summary(tmp_path):
    db=tmp_path/'pipeline.db'; csv_path=tmp_path/'source.csv'
    pd.DataFrame([{"post_id":"run1","platform":"LinkedIn","username":"maker","text":"A useful and excellent update","created_at":"2025-05-01T12:00:00Z","likes":5,"comments":1,"shares":2,"hashtags":"#work"}]).to_csv(csv_path,index=False)
    client=create_app({"TESTING":True,"DATABASE_PATH":db,"RAW_DATA_PATH":csv_path}).test_client()
    response=client.post('/api/pipeline/run')
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success'
    assert payload['records_loaded']==1 and payload['records_processed']==1 and payload['records_failed']==0
    repeated=client.post('/api/pipeline/run').get_json()
    assert repeated['new_records']==0 and repeated['duplicate_records']==1 and repeated['processed_records']==0
    assert client.get('/api/pipeline/runs').get_json()[0]['source']=='csv'
