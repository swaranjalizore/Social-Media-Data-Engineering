"""Local source abstraction for CSV and JSON post files."""
from pathlib import Path
import json
import pandas as pd
from config import RAW_DATA_PATH, ROOT_DIR

JSON_DATA_PATH = ROOT_DIR / "data" / "raw" / "social_media_posts.json"

def load_source(source="csv", path=None):
    """Read a local CSV or JSON dataset into a DataFrame."""
    kind = str(source).lower()
    if kind not in {"csv", "json"}:
        raise ValueError("Unsupported source. Choose 'csv' or 'json'.")
    selected = Path(path) if path is not None else (RAW_DATA_PATH if kind == "csv" else JSON_DATA_PATH)
    if not selected.is_file():
        raise FileNotFoundError(f"{kind.upper()} source file not found: {selected}")
    try:
        if kind == "csv":
            return pd.read_csv(selected)
        with selected.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("JSON source must contain a list of post objects.")
        return pd.DataFrame(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read {kind.upper()} source {selected}: {exc}") from exc
