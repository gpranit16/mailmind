"""Offline sentiment analysis utilities using VADER."""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment(email_text: str) -> tuple[str, float]:
	"""Analyze raw email text and return (sentiment_label, compound_score).

	Labeling rules:
	- compound >= 0.05  -> positive
	- compound <= -0.05 -> negative
	- otherwise         -> neutral
	"""
	if not isinstance(email_text, str):
		raise TypeError("email_text must be a string")

	scores = _analyzer.polarity_scores(email_text)
	compound_score = float(scores["compound"])

	if compound_score >= 0.05:
		sentiment_label = "positive"
	elif compound_score <= -0.05:
		sentiment_label = "negative"
	else:
		sentiment_label = "neutral"

	return sentiment_label, compound_score


if __name__ == "__main__":
	sample_email_text = (
		"Hi team, thank you for the quick support yesterday. "
		"The issue is fully resolved and everything works great now!"
	)

	label, compound = analyze_sentiment(sample_email_text)
	print("Sentiment Label:", label)
	print("Compound Score:", compound)
