"""Reusable record-level data quality checks."""
import pandas as pd
from config import VALID_PLATFORMS
from pipeline.cleaning import REQUIRED_COLUMNS

def quality_report(frame):
    """Validate source rows before cleanup so no quality issue is hidden."""
    errors = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        errors.append({"row": None, "field": "columns", "message": f"Missing required columns: {', '.join(missing_columns)}"})
    invalid_rows = set(frame.index) if missing_columns else set()
    missing_rows = set()
    missing_values = 0
    invalid_platforms = 0
    invalid_engagement_values = 0
    invalid_sentiments = 0
    missing_by_column = {column: 0 for column in REQUIRED_COLUMNS}
    for index, row in frame.iterrows():
        checks = []
        for column in REQUIRED_COLUMNS:
            if column not in frame.columns or pd.isna(row.get(column)) or str(row.get(column, "")).strip() == "":
                missing_values += 1
                missing_by_column[column] += 1
                missing_rows.add(index)
        if not str(row.get("post_id", "")).strip(): checks.append(("post_id", "post_id is missing"))
        if not str(row.get("username", "")).strip(): checks.append(("username", "username is missing"))
        if not str(row.get("text", "")).strip(): checks.append(("text", "text is empty"))
        platform = str(row.get("platform", "")).strip().lower()
        if platform == "twitter": platform = "x"
        allowed = {value.lower() for value in VALID_PLATFORMS}
        if platform not in allowed:
            invalid_platforms += 1
            checks.append(("platform", "platform is not supported"))
        if pd.isna(pd.to_datetime(row.get("created_at", ""), errors="coerce", utc=True)):
            checks.append(("created_at", "created_at is not a valid date"))
        for column in ("likes", "comments", "shares"):
            try:
                value = float(row.get(column))
                if not pd.notna(value) or value < 0: raise ValueError
            except (TypeError, ValueError):
                invalid_engagement_values += 1
                checks.append((column, f"{column} must be numeric and non-negative"))
        if "sentiment" in frame.columns and str(row.get("sentiment", "")).strip() not in {"Positive", "Neutral", "Negative"}:
            invalid_sentiments += 1
            checks.append(("sentiment", "sentiment must be Positive, Neutral, or Negative"))
        if checks:
            invalid_rows.add(index)
            errors.extend({"row": int(index), "field": field, "message": message} for field, message in checks)
    ids = frame["post_id"].fillna("").astype(str).str.strip() if "post_id" in frame else pd.Series(dtype=str)
    duplicate_mask = ids.ne("") & ids.duplicated(keep="first")
    duplicate_indices = list(ids.index[duplicate_mask])
    for index in duplicate_indices:
        invalid_rows.add(index)
        errors.append({"row": int(index), "field": "post_id", "message": "duplicate post_id"})
    invalid_count = len(invalid_rows)
    total = len(frame)
    affected_rows = invalid_rows | missing_rows | set(duplicate_indices)
    ratio = len(affected_rows) / total if total else 0
    status = "PASS" if not affected_rows else ("WARNING" if ratio <= 0.05 else "FAIL")
    return {
        "total_records": total,
        "valid_records": total - invalid_count,
        "invalid_records": invalid_count,
        "quality_percentage": round(100 * (total - invalid_count) / total, 2) if total else 100.0,
        "missing_values": missing_values,
        "missing_by_column": missing_by_column,
        "missing_value_records": len(missing_rows),
        "duplicate_records": len(duplicate_indices),
        "invalid_platforms": invalid_platforms,
        "invalid_engagement_values": invalid_engagement_values,
        "invalid_sentiments": invalid_sentiments,
        "quality_status": status,
        "errors": errors,
        "warnings": [],
        "invalid_indices": sorted(int(i) for i in invalid_rows),
    }

def validate_posts(frame, missing_columns=None):
    """Compatibility wrapper returning the original validation keys too."""
    report = quality_report(frame)
    if missing_columns:
        report["errors"].append({"row": None, "field": "columns", "message": f"Missing required columns: {', '.join(missing_columns)}"})
        report["invalid_records"] = len(frame)
        report["valid_records"] = 0
    return report
