"""Non-destructive cleaning for input post records."""
import re
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["post_id", "platform", "username", "text", "created_at", "likes", "comments", "shares", "hashtags"]

def clean_posts(frame):
    data = frame.copy()
    for col in REQUIRED_COLUMNS:
        if col not in data.columns: data[col] = np.nan
    data = data.drop_duplicates(subset=["post_id"], keep="first")
    for col in ("post_id", "username", "text", "platform", "hashtags"):
        data[col] = data[col].fillna("").astype(str).str.strip()
    data["text"] = data["text"].str.replace(r"\s+", " ", regex=True)
    data["username"] = data["username"].str.lstrip("@").str.lower()
    data["platform"] = data["platform"].str.strip().str.lower().replace({"twitter":"x"})
    platform_names = {"instagram":"Instagram", "x":"X", "facebook":"Facebook", "linkedin":"LinkedIn"}
    data["platform"] = data["platform"].replace(platform_names)
    data["hashtags"] = data["hashtags"].apply(lambda value: " ".join("#" + tag.lstrip("#").lower() for tag in re.findall(r"#?[\w]+", value, flags=re.UNICODE)))
    for col in ("likes", "comments", "shares"):
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0).clip(lower=0).astype(int)
    data["created_at"] = pd.to_datetime(data["created_at"], errors="coerce", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    data.loc[data["created_at"].isna(), "created_at"] = ""
    return data.reset_index(drop=True)
