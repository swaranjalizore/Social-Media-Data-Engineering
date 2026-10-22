"""Project configuration and paths."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "database/social_media.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT_DIR / DATABASE_PATH
RAW_DATA_PATH = ROOT_DIR / "data" / "raw" / "social_media_posts.csv"
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes"}
VALID_PLATFORMS = {"Instagram", "X", "Facebook", "LinkedIn"}
DEFAULT_DATA_SOURCE = os.getenv("DEFAULT_DATA_SOURCE", "csv").lower()
PIPELINE_BATCH_SIZE = max(1, int(os.getenv("PIPELINE_BATCH_SIZE", "250")))
