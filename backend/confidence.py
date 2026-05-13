"""Confidence-based action routing utilities."""


def decide_action(confidence_score: float) -> str:
	"""Decide action based on confidence percentage.

	Rules:
	- >= 85: auto_send
	- >= 60 and < 85: flag_review
	- < 60: escalate_human
	"""
	score = float(confidence_score)

	if score >= 85:
		return "auto_send"
	if score >= 60:
		return "flag_review"
	return "escalate_human"


def get_action_message(action: str) -> str:
	"""Return user-facing message for an action."""
	if action == "auto_send":
		return "Reply will be sent automatically"
	if action == "flag_review":
		return "Reply needs your approval before sending"
	if action == "escalate_human":
		return "This email needs human attention"
	return "Unknown action"


if __name__ == "__main__":
	test_scores = [90, 75, 45]

	for score in test_scores:
		action = decide_action(score)
		message = get_action_message(action)
		print(f"Score: {score} -> Action: {action} | Message: {message}")
