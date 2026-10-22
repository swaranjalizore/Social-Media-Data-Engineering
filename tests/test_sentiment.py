from sentiment.analyzer import analyze_sentiment

def test_sentiment_classification():
    assert analyze_sentiment('I absolutely love this wonderful result')['sentiment']=='Positive'
    assert analyze_sentiment('I hate this terrible experience')['sentiment']=='Negative'
    assert analyze_sentiment('The meeting starts at noon')['sentiment']=='Neutral'
