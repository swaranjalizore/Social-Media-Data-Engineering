# Social Media Data Engineering & Sentiment Analytics Platform

A local MCA Data Science / Data Engineering project for processing fictional social posts, recording quality and pipeline audit information, and exploring sentiment and engagement metrics. The project uses no paid API, credentials, or live social-media service. Sample files and browser libraries are stored locally.

## Objective and problem statement

Social posts contain inconsistent text and engagement values. This project demonstrates a repeatable way to ingest local files, validate and transform records, analyze sentiment, store them in SQLite, and expose trustworthy summaries to a dashboard and API.

## Features

- CSV and JSON source abstraction with bundled fictional sample datasets.
- Incremental batch runs: previously stored post IDs are counted as duplicates and not inserted again.
- Record-level quality reports, data-quality status, and pipeline-run audit history.
- Cleaning, engagement and text features, and TextBlob sentiment enrichment.
- Operational SQLite `posts` table plus a small fact/dimension reporting model.
- SQL KPIs, platform comparisons, sentiment and time trends, hashtag analysis, and top posts.
- Responsive, filterable dashboard with CSV download.
- All dashboard CSS and JavaScript libraries are served locally for offline use.

## Architecture and data processing

```text
Local CSV / JSON
       ↓
Source loader → quality validation → cleaning → batch transformations
       ↓
TextBlob sentiment → SQLite posts + fact/dimension warehouse + run audit
       ↓
SQL analytics → Flask JSON API / CSV export → local Bootstrap + Chart.js dashboard
```

Quality checks count missing values by field and record, duplicates, invalid platforms/dates/engagement values, and invalid sentiment labels when supplied. Quality percentage is the share of records passing hard validation. PASS means no affected records; WARNING means at most 5% are affected; FAIL means more than 5%. Valid rows continue through processing when other rows fail.

Cleaning normalizes whitespace, usernames, platforms, dates, numeric metrics, and hashtags. Transformations add `engagement_total`, a batch-normalized `engagement_rate` index, hashtag count, text length, word count, post date, hour, and weekday. Since follower/impression data is unavailable, engagement rate is not a reach-based rate. TextBlob polarity is labelled Positive above `0.05`, Negative below `-0.05`, otherwise Neutral; this simple estimate can miss context and sarcasm.

The operational `posts` table is supported by `dim_platform`, `dim_date`, `fact_social_posts`, and `post_hashtags`. The `pipeline_runs` table records source, status, timing, input/new/duplicate/processed/failed counts, and quality details. Existing Task 1 databases are migrated and backfilled when initialized.

## Technologies

Python 3.11+, Flask, Pandas, NumPy, TextBlob, SQLite, HTML5, CSS3, Bootstrap 5, JavaScript, Chart.js, pytest, and python-dotenv. No machine-learning classifier is used in this project; TextBlob provides the requested simple sentiment analysis. Bootstrap and Chart.js are bundled under `static/vendor` with their licenses; runtime pages need no CDN access.

## Project structure

```text
app.py, config.py, requirements.txt, README.md, .env.example
analytics/                 SQL analytics and dashboard data preparation
database/                  schema, migration, SQLite and warehouse loading
data/raw/                  fictional CSV and JSON samples
data/processed/            generated processed and analytical CSV exports
pipeline/                  source, ingestion, quality, cleaning, transforms, orchestration
sentiment/                 TextBlob sentiment analysis
templates/                 landing page and dashboard
static/css, static/js/     page styling and dashboard logic
static/vendor/             local Bootstrap, Chart.js, license notices
tests/                     Task 1–3 pytest coverage
```

## Install and run on Windows

From the project directory, using Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "from pipeline.pipeline import run_pipeline; print(run_pipeline())"
python app.py
```

Open `http://127.0.0.1:5000`. The CSV source is the default. To ingest the bundled JSON file, run `python -c "from pipeline.pipeline import run_pipeline; print(run_pipeline(source='json'))"` or POST `{"source":"json"}` to `/api/pipeline/run`.

Configuration is in `.env`: `DATABASE_PATH`, `DEBUG` (off by default), `DEFAULT_DATA_SOURCE`, and `PIPELINE_BATCH_SIZE`. SQLite defaults to `database/social_media.db`. Processed and warehouse exports are written to `data/processed/`.

## Dashboard and filters

The dashboard displays total posts and engagement, average engagement/index/polarity, platform and hashtag counts, sentiment distribution/trend, platform performance, engagement by date/hour/weekday, hashtag usage and average engagement, top-performing posts, quality details, and recent pipeline runs. Filters for platform, sentiment, and date range update analytics and the export link. The pipeline button runs the local CSV batch and refreshes the dashboard.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` or `/api/status` | Service and database status |
| POST | `/api/pipeline/run` | Run pipeline; optional `{"source":"csv"}` or `{"source":"json"}` |
| GET | `/api/summary` | Overall KPI summary |
| GET | `/api/sentiment`, `/api/platforms`, `/api/trends`, `/api/hashtags`, `/api/engagement` | Existing sentiment, platform, trend, hashtag, and engagement analytics |
| GET | `/api/quality` | Latest quality report and stored-data checks |
| GET | `/api/pipeline/runs?limit=10` | Recent audit runs; limit range 1–100 |
| GET | `/api/top-posts?limit=10` | Most engaging posts |
| GET | `/api/analytics/dashboard` | Combined filtered analytics payload |
| GET | `/api/analytics/kpis`, `/api/analytics/platforms`, `/api/analytics/sentiment` | Filtered KPI and comparison metrics |
| GET | `/api/analytics/engagement/date`, `/hour`, `/weekday` | Time-based post and engagement metrics |
| GET | `/api/analytics/hashtags`, `/api/analytics/hashtags/engagement` | Hashtag usage and average engagement |
| GET | `/api/export` | Download processed CSV; accepts dashboard filters |

Filtered analytics/export endpoints accept optional `platform`, `sentiment`, `start_date=YYYY-MM-DD`, and `end_date=YYYY-MM-DD`. Invalid values and reversed date ranges return HTTP 400 JSON errors.

## Tests

```powershell
python -m pytest --basetemp="$env:USERPROFILE\pytest-temp-social-media"
```

The tests use temporary local CSV/JSON/SQLite data and no external service. If that path already contains files you need to keep, choose a new writable path instead. Pytest's cache provider is disabled to avoid the known Windows cache-directory permission issue.

## Example pipeline workflow

```powershell
python -c "from pipeline.pipeline import run_pipeline; print(run_pipeline())"
python -c "from pipeline.pipeline import run_pipeline; print(run_pipeline())"  # repeat: existing IDs count as duplicates
python -c "from pipeline.pipeline import run_pipeline; print(run_pipeline(source='json'))"
python app.py
```

The bundled CSV contains 180 fictional records and the JSON sample adds a small local batch. The project demonstrates ETL, batch and incremental processing, validation, data quality, transformations, sentiment enrichment, fact/dimension tables, SQL analytics, monitoring/audit lineage, API access, and automated testing. It is an educational local application, not a production cloud system.
