"""TextBlob polarity sentiment; scores near zero are neutral."""
from textblob import TextBlob

NEUTRAL_THRESHOLD = 0.05

def analyze_sentiment(text):
    analysis = TextBlob(str(text)).sentiment
    polarity = float(analysis.polarity)
    label = "Positive" if polarity > NEUTRAL_THRESHOLD else "Negative" if polarity < -NEUTRAL_THRESHOLD else "Neutral"
    return {"sentiment": label, "sentiment_score": polarity, "subjectivity": float(analysis.subjectivity)}

def analyze_frame(frame):
    result = frame.copy()
    scores = result["text"].apply(analyze_sentiment)
    result["sentiment"] = scores.apply(lambda x:x["sentiment"])
    result["sentiment_score"] = scores.apply(lambda x:x["sentiment_score"])
    result["subjectivity"] = scores.apply(lambda x:x["subjectivity"])
    return result
