"""Local Flask interface for the social media analytics pipeline."""
import logging
from datetime import date
from io import BytesIO

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from analytics.queries import (
    fetch_advanced_kpis, fetch_dashboard_analytics, fetch_data_quality_summary,
    fetch_daily_engagement, fetch_daily_volume, fetch_filtered_engagement_by_date,
    fetch_filtered_platform_analytics, fetch_filtered_sentiment_distribution,
    fetch_filtered_sentiment_trend, fetch_filtered_top_posts, fetch_hashtag_engagement,
    fetch_hashtag_usage, fetch_platform_performance, fetch_posts_by_hour,
    fetch_posts_by_weekday, fetch_recent_pipeline_runs, fetch_sentiment_by_platform,
    fetch_filtered_export,
)
from config import DATABASE_PATH, DEBUG, RAW_DATA_PATH, VALID_PLATFORMS
from database.db import database_initialized, initialize_database
from pipeline.pipeline import run_pipeline

logger = logging.getLogger(__name__)
VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}

def _error(message, status):
    return jsonify({"status": "error", "error": message}), status

def _analytics_filters():
    filters = {}
    platform = request.args.get("platform", "").strip()
    if platform:
        canonical = {value.casefold(): value for value in VALID_PLATFORMS}
        if platform.casefold() not in canonical:
            return None, _error("Invalid platform filter.", 400)
        filters["platform"] = canonical[platform.casefold()]
    sentiment = request.args.get("sentiment", "").strip()
    if sentiment:
        canonical = {value.casefold(): value for value in VALID_SENTIMENTS}
        if sentiment.casefold() not in canonical:
            return None, _error("Invalid sentiment filter.", 400)
        filters["sentiment"] = canonical[sentiment.casefold()]
    parsed_dates = {}
    for key, label in (("start_date", "start date"), ("end_date", "end date")):
        raw_value = request.args.get(key, "").strip()
        if raw_value:
            try:
                parsed_dates[key] = date.fromisoformat(raw_value).isoformat()
            except ValueError:
                return None, _error(f"Invalid {label}; use YYYY-MM-DD.", 400)
    if parsed_dates.get("start_date") and parsed_dates.get("end_date") and parsed_dates["start_date"] > parsed_dates["end_date"]:
        return None, _error("start_date must be on or before end_date.", 400)
    filters.update(parsed_dates)
    return filters, None

def _limit(default=10):
    raw = request.args.get("limit", str(default))
    try:
        value = int(raw)
    except ValueError:
        return None, _error("limit must be an integer between 1 and 100.", 400)
    if not 1 <= value <= 100:
        return None, _error("limit must be an integer between 1 and 100.", 400)
    return value, None

def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.update(DATABASE_PATH=DATABASE_PATH, RAW_DATA_PATH=RAW_DATA_PATH, TESTING=False)
    if config_overrides:
        app.config.update(config_overrides)
    db_path = app.config["DATABASE_PATH"]
    if database_initialized(db_path):
        initialize_database(db_path)

    @app.errorhandler(HTTPException)
    def api_http_error(error):
        if request.path.startswith("/api/"):
            return _error(error.description, error.code or 500)
        return error

    @app.errorhandler(Exception)
    def api_unexpected_error(error):
        logger.exception("Unhandled request error", exc_info=error)
        if request.path.startswith("/api/"):
            return _error("Internal server error. Check the application log.", 500)
        return "Internal Server Error", 500

    @app.before_request
    def ensure_api_schema():
        if request.path.startswith("/api/") and request.path != "/api/health" and not database_initialized(db_path):
            initialize_database(db_path)

    @app.get("/")
    def index():
        return render_template("index.html", initialized=database_initialized(db_path))

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html", platforms=sorted(VALID_PLATFORMS))

    @app.get("/api/health")
    @app.get("/api/status")
    def health():
        return jsonify({"status": "ok", "database_initialized": database_initialized(db_path)})

    @app.post("/api/pipeline/run")
    def pipeline_run():
        if request.is_json:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return _error("Request JSON must be a valid object.", 400)
        else:
            payload = {}
        if not isinstance(payload, dict):
            return _error("Request JSON must be an object.", 400)
        source = payload.get("source")
        if source is not None and str(source).lower() not in {"csv", "json"}:
            return _error("source must be 'csv' or 'json'.", 400)
        try:
            return jsonify(run_pipeline(app.config["RAW_DATA_PATH"], db_path, source=source)), 200
        except Exception:
            logger.exception("API pipeline run failed")
            return _error("Pipeline could not be completed. Check the application log.", 500)

    @app.get("/api/summary")
    def summary():
        return jsonify(fetch_advanced_kpis(db_path=db_path))

    @app.get("/api/sentiment")
    def sentiment():
        return jsonify(fetch_filtered_sentiment_distribution(db_path=db_path))

    @app.get("/api/platforms")
    def platforms():
        return jsonify(fetch_filtered_platform_analytics(db_path=db_path))

    @app.get("/api/trends")
    def trends():
        return jsonify(fetch_filtered_sentiment_trend(db_path=db_path))

    @app.get("/api/hashtags")
    def hashtags():
        return jsonify(fetch_hashtag_usage(db_path=db_path))

    @app.get("/api/engagement")
    def engagement():
        return jsonify(fetch_filtered_platform_analytics(db_path=db_path))

    @app.get("/api/quality")
    def quality():
        return jsonify(fetch_data_quality_summary(db_path))

    @app.get("/api/pipeline/runs")
    def pipeline_runs():
        limit, error = _limit()
        if error:
            return error
        return jsonify(fetch_recent_pipeline_runs(db_path, limit))

    @app.get("/api/top-posts")
    def top_posts():
        filters, error = _analytics_filters()
        if error:
            return error
        limit, error = _limit()
        if error:
            return error
        return jsonify(fetch_filtered_top_posts(filters, db_path, limit))

    @app.get("/api/sentiment/platforms")
    def sentiment_platforms():
        return jsonify(fetch_sentiment_by_platform(db_path))

    @app.get("/api/volume/daily")
    def daily_volume():
        return jsonify(fetch_daily_volume(db_path))

    @app.get("/api/engagement/daily")
    def daily_engagement():
        return jsonify(fetch_daily_engagement(db_path))

    @app.get("/api/platform-performance")
    def platform_performance():
        return jsonify(fetch_platform_performance(db_path))

    @app.get("/api/analytics/dashboard")
    def dashboard_analytics():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_dashboard_analytics(filters, db_path)})

    @app.get("/api/analytics/kpis")
    def analytics_kpis():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_advanced_kpis(filters, db_path)})

    @app.get("/api/analytics/platforms")
    def analytics_platforms():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_filtered_platform_analytics(filters, db_path)})

    @app.get("/api/analytics/sentiment")
    def analytics_sentiment():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_filtered_sentiment_distribution(filters, db_path)})

    @app.get("/api/analytics/engagement/date")
    def analytics_engagement_date():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_filtered_engagement_by_date(filters, db_path)})

    @app.get("/api/analytics/engagement/hour")
    def analytics_engagement_hour():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_posts_by_hour(filters, db_path)})

    @app.get("/api/analytics/engagement/weekday")
    def analytics_engagement_weekday():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_posts_by_weekday(filters, db_path)})

    @app.get("/api/analytics/hashtags")
    def analytics_hashtags():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_hashtag_usage(filters, db_path)})

    @app.get("/api/analytics/hashtags/engagement")
    def analytics_hashtag_engagement():
        filters, error = _analytics_filters()
        if error:
            return error
        return jsonify({"status": "success", "filters": filters, "data": fetch_hashtag_engagement(filters, db_path)})

    @app.get("/api/export")
    def export_csv():
        filters, error = _analytics_filters()
        if error:
            return error
        columns = ["post_id","platform","username","text","created_at","likes","comments","shares","hashtags","engagement_total","engagement_rate","sentiment","polarity","subjectivity","post_date","post_hour","day_of_week","hashtag_count","text_length","word_count"]
        frame = pd.DataFrame(fetch_filtered_export(filters, db_path), columns=columns)
        buffer = BytesIO(frame.to_csv(index=False).encode("utf-8-sig"))
        return send_file(buffer, mimetype="text/csv; charset=utf-8", as_attachment=True, download_name="social_media_analytics.csv")

    return app

app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.run(debug=DEBUG)
