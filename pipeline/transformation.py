"""Derive analysis-ready fields."""
import pandas as pd

def transform_posts(frame, engagement_max=None):
    data = frame.copy()
    for col in ("likes", "comments", "shares"): data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0).clip(lower=0)
    data["engagement"] = data[["likes", "comments", "shares"]].sum(axis=1).astype(int)
    data["engagement_total"] = data["engagement"]
    # No follower/impression count is present in the source. This is a within-batch
    # normalized engagement index (0..1), rather than a conventional reach rate.
    observed_max = int(data["engagement"].max()) if not data.empty else 0
    maximum = max(int(engagement_max if engagement_max is not None else observed_max), 1)
    data["engagement_rate"] = (data["engagement"] / maximum).astype(float)
    hashtags = data.get("hashtags", pd.Series("", index=data.index))
    text = data.get("text", pd.Series("", index=data.index))
    data["hashtag_count"] = hashtags.fillna("").astype(str).apply(lambda value: sum(1 for token in value.split() if token.startswith("#")))
    data["text_length"] = text.fillna("").astype(str).str.len()
    data["word_count"] = text.fillna("").astype(str).str.split().str.len()
    dates = pd.to_datetime(data["created_at"], errors="coerce", utc=True)
    data["date"] = dates.dt.strftime("%Y-%m-%d")
    data["month"] = dates.dt.strftime("%Y-%m")
    data["day"] = dates.dt.strftime("%A")
    data["post_date"] = data["date"]
    data["post_hour"] = dates.dt.hour.fillna(0).astype(int)
    data["day_of_week"] = data["day"]
    return data
