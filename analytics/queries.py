"""SQL analytics kept separate from Flask route handlers."""
from database.db import (_rows, fetch_summary, fetch_sentiment_summary,
                         fetch_platform_summary, fetch_daily_sentiment_trend,
                         fetch_top_hashtags, fetch_engagement_statistics)

def _where(filters=None, alias="p"):
    """Build a parameterized predicate for optional platform/sentiment/date filters."""
    filters = filters or {}
    clauses, params = [], []
    for key, column in (("platform", "platform"), ("sentiment", "sentiment")):
        if filters.get(key):
            clauses.append(f"{alias}.{column}=?")
            params.append(filters[key])
    if filters.get("start_date"):
        clauses.append(f"{alias}.post_date>=?")
        params.append(filters["start_date"])
    if filters.get("end_date"):
        clauses.append(f"{alias}.post_date<=?")
        params.append(filters["end_date"])
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

def fetch_advanced_kpis(filters=None, db_path=None):
    where, params = _where(filters)
    rows = _rows("SELECT COUNT(*) total_posts,COALESCE(SUM(p.engagement_total),0) total_engagement,COALESCE(AVG(p.engagement_total),0) average_engagement,COALESCE(AVG(p.engagement_rate),0) average_engagement_rate,COALESCE(AVG(p.polarity),0) average_sentiment_polarity,COUNT(DISTINCT p.platform) total_platforms,COALESCE(SUM(p.sentiment='Positive'),0) positive_posts,COALESCE(SUM(p.sentiment='Neutral'),0) neutral_posts,COALESCE(SUM(p.sentiment='Negative'),0) negative_posts FROM posts p" + where, params, db_path)
    hashtag_where, hashtag_params = _where(filters, "p")
    hashtag_rows = _rows("SELECT COUNT(DISTINCT h.hashtag) total_hashtags FROM post_hashtags h JOIN posts p USING(post_id)" + hashtag_where, hashtag_params, db_path)
    rows[0]["total_hashtags"] = hashtag_rows[0]["total_hashtags"]
    rows[0]["top_platform"] = _rows("SELECT p.platform FROM posts p" + where + " GROUP BY p.platform ORDER BY COUNT(*) DESC LIMIT 1", params, db_path)[0]["platform"] if rows[0]["total_posts"] else None
    return rows[0]

def fetch_filtered_sentiment_distribution(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.sentiment,COUNT(*) count,ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),2) percentage FROM posts p" + where + " GROUP BY p.sentiment ORDER BY p.sentiment", params, db_path)

def fetch_filtered_platform_analytics(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.platform,COUNT(*) post_count,SUM(p.engagement_total) total_engagement,ROUND(AVG(p.engagement_total),2) average_engagement,ROUND(AVG(p.engagement_rate),4) average_engagement_rate,ROUND(AVG(p.polarity),4) average_sentiment,COALESCE(SUM(p.sentiment='Positive'),0) positive_posts,COALESCE(SUM(p.sentiment='Neutral'),0) neutral_posts,COALESCE(SUM(p.sentiment='Negative'),0) negative_posts FROM posts p" + where + " GROUP BY p.platform ORDER BY total_engagement DESC", params, db_path)

def fetch_filtered_sentiment_trend(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.post_date date,p.sentiment,COUNT(*) count FROM posts p" + where + " GROUP BY p.post_date,p.sentiment ORDER BY p.post_date", params, db_path)

def fetch_filtered_engagement_by_date(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.post_date date,COUNT(*) post_count,SUM(p.engagement_total) total_engagement,ROUND(AVG(p.engagement_total),2) average_engagement FROM posts p" + where + " GROUP BY p.post_date ORDER BY p.post_date", params, db_path)

def fetch_posts_by_hour(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.post_hour hour,COUNT(*) post_count,SUM(p.engagement_total) total_engagement,ROUND(AVG(p.engagement_total),2) average_engagement FROM posts p" + where + " GROUP BY p.post_hour ORDER BY p.post_hour", params, db_path)

def fetch_posts_by_weekday(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.day_of_week day_of_week,COUNT(*) post_count,SUM(p.engagement_total) total_engagement,ROUND(AVG(p.engagement_total),2) average_engagement,MIN(CAST(strftime('%w',p.post_date) AS INTEGER)) weekday_order FROM posts p" + where + " GROUP BY p.day_of_week ORDER BY weekday_order", params, db_path)

def fetch_filtered_top_posts(filters=None, db_path=None, limit=10):
    where, params = _where(filters)
    params.append(int(limit))
    return _rows("SELECT p.post_id,p.platform,p.username,p.text,p.engagement_total engagement,p.sentiment,p.post_date FROM posts p" + where + " ORDER BY p.engagement_total DESC,p.post_id LIMIT ?", params, db_path)

def fetch_hashtag_engagement(filters=None, db_path=None, limit=15):
    where, params = _where(filters, "p")
    params.append(int(limit))
    return _rows("SELECT h.hashtag,COUNT(*) usage_count,SUM(p.engagement_total) total_engagement,ROUND(AVG(p.engagement_total),2) average_engagement FROM post_hashtags h JOIN posts p USING(post_id)" + where + " GROUP BY h.hashtag ORDER BY average_engagement DESC,usage_count DESC LIMIT ?", params, db_path)

def fetch_hashtag_usage(filters=None, db_path=None, limit=15):
    where, params = _where(filters, "p")
    params.append(int(limit))
    return _rows("SELECT h.hashtag,COUNT(*) usage_count FROM post_hashtags h JOIN posts p USING(post_id)" + where + " GROUP BY h.hashtag ORDER BY usage_count DESC,h.hashtag LIMIT ?", params, db_path)

def fetch_dashboard_analytics(filters=None, db_path=None):
    """Prepare the chart/card data contract shared by API and dashboard tests."""
    return {"filters": filters or {}, "kpis": fetch_advanced_kpis(filters, db_path),
            "sentiment": fetch_filtered_sentiment_distribution(filters, db_path),
            "platforms": fetch_filtered_platform_analytics(filters, db_path),
            "sentiment_trend": fetch_filtered_sentiment_trend(filters, db_path),
            "engagement_by_date": fetch_filtered_engagement_by_date(filters, db_path),
            "by_hour": fetch_posts_by_hour(filters, db_path),
            "by_weekday": fetch_posts_by_weekday(filters, db_path),
            "hashtags": fetch_hashtag_usage(filters, db_path),
            "hashtag_engagement": fetch_hashtag_engagement(filters, db_path),
            "top_posts": fetch_filtered_top_posts(filters, db_path)}

def fetch_sentiment_by_platform(db_path=None):
    return _rows("SELECT p.platform_name platform,f.sentiment,COUNT(*) count FROM fact_social_posts f JOIN dim_platform p USING(platform_id) GROUP BY p.platform_name,f.sentiment ORDER BY p.platform_name,f.sentiment", db_path=db_path)

def fetch_daily_volume(db_path=None):
    return _rows("SELECT date_id date,COUNT(*) posts FROM fact_social_posts GROUP BY date_id ORDER BY date_id", db_path=db_path)

def fetch_daily_engagement(db_path=None):
    return _rows("SELECT date_id date,SUM(engagement_total) engagement,ROUND(AVG(engagement_total),2) average_engagement FROM fact_social_posts GROUP BY date_id ORDER BY date_id", db_path=db_path)

def fetch_platform_performance(db_path=None):
    return _rows("SELECT p.platform_name platform,COUNT(*) posts,ROUND(AVG(f.engagement_total),2) average_engagement,SUM(f.engagement_total) total_engagement,ROUND(AVG(f.sentiment='Positive')*100,1) positive_percent FROM fact_social_posts f JOIN dim_platform p USING(platform_id) GROUP BY p.platform_id ORDER BY total_engagement DESC", db_path=db_path)

def fetch_most_engaging_posts(db_path=None, limit=10):
    return _rows("SELECT post_id,platform,username,text,engagement_total engagement,sentiment,post_date FROM posts ORDER BY engagement_total DESC,post_id LIMIT ?", (int(limit),), db_path)

def fetch_warehouse_export(db_path=None):
    return _rows("SELECT f.post_id,p.platform_name platform,d.date_id post_date,f.likes,f.comments,f.shares,f.engagement_total,f.engagement_rate,f.sentiment,f.polarity,f.subjectivity,f.hashtag_count,f.text_length,f.word_count FROM fact_social_posts f JOIN dim_platform p USING(platform_id) JOIN dim_date d USING(date_id) ORDER BY d.date_id,f.post_id", db_path=db_path)

def fetch_filtered_export(filters=None, db_path=None):
    where, params = _where(filters)
    return _rows("SELECT p.post_id,p.platform,p.username,p.text,p.created_at,p.likes,p.comments,p.shares,p.hashtags,p.engagement_total,p.engagement_rate,p.sentiment,p.polarity,p.subjectivity,p.post_date,p.post_hour,p.day_of_week,p.hashtag_count,p.text_length,p.word_count FROM posts p" + where + " ORDER BY p.post_date,p.post_id", params, db_path)

def fetch_recent_pipeline_runs(db_path=None, limit=10):
    return _rows("SELECT run_id,started_at,completed_at,status,source,total_input,new_records,duplicate_records,processed_records,failed_records,quality_status,execution_seconds,missing_values,missing_value_records,quality_duplicate_records,valid_records,quality_percentage,invalid_records,invalid_platforms,invalid_engagement_values,invalid_sentiments FROM pipeline_runs ORDER BY run_id DESC LIMIT ?", (int(limit),), db_path)

def fetch_data_quality_summary(db_path=None):
    run = _rows("SELECT run_id,started_at,source,total_input,new_records,duplicate_records,processed_records,failed_records,status,quality_status,missing_values,missing_value_records,quality_duplicate_records,valid_records,quality_percentage,invalid_records,invalid_platforms,invalid_engagement_values,invalid_sentiments,missing_by_column_json FROM pipeline_runs ORDER BY run_id DESC LIMIT 1", db_path=db_path)
    stored = _rows("SELECT COUNT(*) total_posts,COALESCE(SUM(engagement_total<0),0) invalid_engagement_rows,COALESCE(SUM(sentiment NOT IN ('Positive','Neutral','Negative')),0) invalid_sentiment_rows FROM posts", db_path=db_path)
    latest = run[0] if run else None
    if latest:
        import json
        latest["missing_by_column"] = json.loads(latest.pop("missing_by_column_json") or "{}")
    return {"latest_run":latest, "stored":stored[0]}

__all__ = ["fetch_summary", "fetch_sentiment_summary", "fetch_platform_summary",
           "fetch_daily_sentiment_trend", "fetch_top_hashtags", "fetch_engagement_statistics",
           "fetch_sentiment_by_platform", "fetch_daily_volume", "fetch_daily_engagement",
           "fetch_platform_performance", "fetch_most_engaging_posts", "fetch_recent_pipeline_runs",
           "fetch_data_quality_summary", "fetch_warehouse_export", "fetch_filtered_export", "fetch_advanced_kpis",
           "fetch_filtered_sentiment_distribution", "fetch_filtered_platform_analytics",
           "fetch_filtered_sentiment_trend", "fetch_filtered_engagement_by_date",
           "fetch_posts_by_hour", "fetch_posts_by_weekday", "fetch_filtered_top_posts",
           "fetch_hashtag_engagement", "fetch_hashtag_usage", "fetch_dashboard_analytics"]
