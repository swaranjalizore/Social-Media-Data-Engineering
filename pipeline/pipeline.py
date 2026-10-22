"""Incremental, batch-oriented ETL pipeline orchestration."""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from config import RAW_DATA_PATH, PROCESSED_DATA_DIR, DATABASE_PATH, DEFAULT_DATA_SOURCE, PIPELINE_BATCH_SIZE
from database.db import initialize_database, insert_posts, insert_pipeline_run, existing_post_ids, fetch_posts
from pipeline.source import load_source
from pipeline.cleaning import clean_posts
from pipeline.validation import quality_report
from pipeline.transformation import transform_posts
from sentiment.analyzer import analyze_frame
from analytics.queries import fetch_warehouse_export

logger = logging.getLogger(__name__)

def _time_now(): return datetime.now(timezone.utc).isoformat()

def run_pipeline(csv_path=RAW_DATA_PATH, db_path=DATABASE_PATH, save_processed=True, source=None, batch_size=None, processed_dir=None):
    """Run a local CSV/JSON batch, skipping invalid and previously stored posts.

    csv_path remains the second positional argument for Task 1 compatibility.
    """
    started_clock = time.perf_counter()
    database_target = Path(db_path or DATABASE_PATH).resolve()
    default_database = Path(DATABASE_PATH).resolve()
    output_dir = Path(processed_dir) if processed_dir is not None else (PROCESSED_DATA_DIR if database_target == default_database else database_target.parent / "processed")
    source_name = (source or DEFAULT_DATA_SOURCE).lower()
    explicit_path = csv_path if source is None or Path(csv_path) != Path(RAW_DATA_PATH) else None
    run = {"started_at": _time_now(), "completed_at": None, "source": source_name,
           "total_input": 0, "new_records": 0, "duplicate_records": 0,
           "processed_records": 0, "failed_records": 0, "quality_status": "FAIL",
           "execution_seconds": 0.0, "error_message": None, "status": "failed",
           "records_loaded": 0, "records_processed": 0, "records_failed": 0}
    try:
        initialize_database(db_path)
        logger.info("Pipeline ingest from %s", source_name)
        raw = load_source(source_name, explicit_path)
        run["total_input"] = run["records_loaded"] = len(raw)
        quality = quality_report(raw)
        run["quality_status"] = quality["quality_status"]
        for metric in ("missing_values", "missing_value_records", "invalid_records", "valid_records", "invalid_platforms", "invalid_engagement_values", "invalid_sentiments", "quality_percentage"):
            run[metric] = quality[metric]
        run["quality_duplicate_records"] = quality["duplicate_records"]
        run["missing_by_column"] = quality["missing_by_column"]
        invalid_indices = set(quality["invalid_indices"])
        # Repeated IDs in the same file count as duplicate records, not failed rows.
        raw_ids = raw["post_id"].fillna("").astype(str).str.strip() if "post_id" in raw else pd.Series("", index=raw.index)
        within_batch_duplicates = int((raw_ids.ne("") & raw_ids.duplicated(keep="first")).sum())
        invalid_nonduplicates = {i for i in invalid_indices if i not in set(raw_ids.index[raw_ids.ne("") & raw_ids.duplicated(keep="first")])}
        valid_source = raw.drop(index=list(invalid_nonduplicates), errors="ignore")
        cleaned = clean_posts(valid_source)
        present_ids = existing_post_ids(db_path)
        already_stored = cleaned["post_id"].isin(present_ids)
        db_duplicates = int(already_stored.sum())
        candidates = cleaned.loc[~already_stored].reset_index(drop=True)
        run["duplicate_records"] = within_batch_duplicates + db_duplicates
        run["new_records"] = len(candidates)
        run["failed_records"] = run["records_failed"] = len(invalid_nonduplicates)
        size = max(1, int(batch_size or PIPELINE_BATCH_SIZE))
        if candidates.empty:
            engagement_max = 0
        else:
            engagement_max = int(pd.concat([pd.to_numeric(candidates[column], errors="coerce").fillna(0).clip(lower=0) for column in ("likes", "comments", "shares")], axis=1).sum(axis=1).max())
        for start in range(0, len(candidates), size):
            batch = candidates.iloc[start:start + size].copy()
            transformed = transform_posts(batch, engagement_max=engagement_max)
            enriched = analyze_frame(transformed)
            inserted = insert_posts(enriched, db_path)
            run["processed_records"] += inserted
        run["records_processed"] = run["processed_records"]
        # A conflict can only occur if another writer inserted an ID after the check.
        run["failed_records"] = run["records_failed"] = max(run["failed_records"], run["new_records"] - run["processed_records"])
        if run["failed_records"]: run["quality_status"] = "WARNING" if run["quality_status"] == "PASS" else run["quality_status"]
        run["status"] = "success" if run["failed_records"] == 0 else "completed_with_errors"
        run["quality_report"] = {key: value for key, value in quality.items() if key != "invalid_indices"}
        if save_processed:
            output_dir.mkdir(parents=True, exist_ok=True)
            analytical = fetch_posts(db_path, limit=1_000_000)
            analytical.to_csv(output_dir / "social_media_posts_processed.csv", index=False)
            pd.DataFrame(fetch_warehouse_export(db_path)).to_csv(output_dir / "social_media_analytics.csv", index=False)
        logger.info("Pipeline complete: %s", {key:run[key] for key in ("status","total_input","new_records","duplicate_records","processed_records","failed_records","quality_status")})
        return run
    except Exception as exc:
        run["error_message"] = str(exc)
        logger.exception("Pipeline failed")
        raise
    finally:
        run["completed_at"] = _time_now()
        run["execution_seconds"] = round(time.perf_counter() - started_clock, 4)
        try: insert_pipeline_run(run, db_path)
        except Exception: logger.exception("Could not record pipeline run")
