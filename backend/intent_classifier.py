"""Intent classification using sentence-transformers + SVM.

Features:
- Manual training data for 7 intents (>=15 examples each)
- Embeddings from all-MiniLM-L6-v2
- SVM (RBF kernel) training
- Accuracy reporting
- Saved model to models/intent_model.pkl
- classify_intent(email_text) inference helper
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC


BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "intent_model.pkl"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TEST_SIZE = 0.2
RANDOM_STATE = 42

_embedding_model: SentenceTransformer | None = None
_intent_model: SVC | None = None


def _get_embedding_model() -> SentenceTransformer:
	"""Lazily load and cache embedding model."""
	global _embedding_model
	if _embedding_model is None:
		_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
	return _embedding_model


def get_training_data() -> Tuple[List[str], List[str]]:
	"""Return manual training samples and labels for all 7 intents."""
	samples_by_intent: Dict[str, List[str]] = {
		"meeting_request": [
			"Can we schedule a meeting for tomorrow at 10 AM?",
			"Please arrange a call with the finance team this afternoon.",
			"I would like to book a meeting slot for next Monday.",
			"Let us set up a quick sync on project milestones.",
			"Could you confirm availability for a team meeting this week?",
			"Can we meet to discuss the quarterly budget plan?",
			"Please schedule a Zoom meeting with the client.",
			"I need a calendar invite for our strategy discussion.",
			"Let us have a catch-up meeting regarding deliverables.",
			"Please find a suitable time for a department meeting.",
			"Can we plan a one-on-one meeting this evening?",
			"Arrange a review meeting with product and engineering.",
			"Would Thursday work for a project kickoff meeting?",
			"Please organize a meeting to finalize the proposal.",
			"Can we have a brief meeting after lunch?",
		],
		"complaint": [
			"I am very disappointed with the delay in service.",
			"Your support team has not responded for three days.",
			"The product quality was poor and unacceptable.",
			"I want to report a complaint about repeated billing errors.",
			"This issue has happened again and I am frustrated.",
			"The shipment arrived damaged and incomplete.",
			"I am unhappy with how my request was handled.",
			"The app keeps crashing and no one has fixed it.",
			"I expected better service from your company.",
			"The promised refund has still not been processed.",
			"I am filing a complaint regarding rude customer service.",
			"This is unacceptable and needs immediate correction.",
			"My order was incorrect and support was unhelpful.",
			"The response I received did not solve anything.",
			"I am not satisfied with the resolution provided.",
		],
		"inquiry": [
			"Could you share details about your pricing plans?",
			"I would like to know if this feature is available.",
			"Can you explain how the onboarding process works?",
			"Please provide information on enterprise subscriptions.",
			"Is there a discount for annual billing?",
			"Can you tell me the expected delivery timeline?",
			"I have a question about your integration options.",
			"What documents are required to complete registration?",
			"Could you clarify the warranty terms for this product?",
			"Please let me know whether weekend support is available.",
			"Do you offer custom reporting in the dashboard?",
			"Can you provide the technical specifications sheet?",
			"I am checking if your service is available in my region.",
			"What are the payment methods you currently accept?",
			"Could you send more information about training sessions?",
		],
		"follow_up": [
			"Just following up on the proposal sent last week.",
			"Any update on my previous email regarding approval?",
			"I wanted to check the status of the pending request.",
			"Following up to see if you had a chance to review this.",
			"Can you share an update on the ticket I raised?",
			"This is a gentle reminder about my earlier message.",
			"Please let me know if there is progress on this task.",
			"Checking in again on the contract feedback.",
			"I am writing to follow up on the recruitment update.",
			"Have you had time to review the attached document?",
			"Circling back on the action items from our last discussion.",
			"Any news regarding the shipment confirmation?",
			"Following up to confirm if the invoice was received.",
			"Please update me on the implementation timeline.",
			"Kind reminder to share your response on this matter.",
		],
		"feedback": [
			"Great work by the team on the recent release.",
			"I appreciate the smooth onboarding experience.",
			"The new dashboard looks clean and very helpful.",
			"I have some suggestions to improve the reporting module.",
			"Overall the training session was informative and engaging.",
			"Your customer support was polite and effective.",
			"The latest update improved performance significantly.",
			"I would recommend adding dark mode for better usability.",
			"Thank you for listening to our earlier suggestions.",
			"The interface is intuitive but search could be faster.",
			"I liked the webinar and found it very practical.",
			"The documentation is clear and easy to follow.",
			"Feature navigation has become much better now.",
			"Please consider adding export to PDF in future updates.",
			"The support article quality is excellent.",
		],
		"urgent": [
			"Urgent: production server is down right now.",
			"Please respond immediately, this is critical.",
			"Need immediate assistance with payment failure issue.",
			"This requires urgent attention before end of day.",
			"High priority: client-facing bug must be fixed now.",
			"Emergency escalation needed for security incident.",
			"ASAP support required for data sync failure.",
			"Critical outage affecting all users right now.",
			"Please treat this as top priority and update immediately.",
			"Urgent request: approve access before 30 minutes.",
			"Immediate action needed on failed deployment.",
			"This is time-sensitive and cannot wait till tomorrow.",
			"Need a rapid response for blocked transaction pipeline.",
			"Please jump on this issue urgently.",
			"Major incident detected, please assist now.",
		],
		"general": [
			"Hope you are doing well and having a great day.",
			"Please find attached the monthly summary report.",
			"Thank you for your help and continued support.",
			"I am sharing the notes from today discussion.",
			"Let me know if you need anything else from my side.",
			"We have completed the documentation as requested.",
			"Here is the updated file for your reference.",
			"Wishing you and your team all the best.",
			"Please acknowledge receipt of this email.",
			"I will be out of office tomorrow afternoon.",
			"Sharing this for your information only.",
			"Thanks again for coordinating with the team.",
			"Kindly review when convenient and share thoughts.",
			"This is just a quick note regarding the schedule.",
			"No immediate action required on this message.",
		],
	}

	texts: List[str] = []
	labels: List[str] = []
	for intent, examples in samples_by_intent.items():
		texts.extend(examples)
		labels.extend([intent] * len(examples))

	return texts, labels


def train_and_save_intent_model(model_path: Path = MODEL_PATH) -> SVC:
	"""Train SVM intent model on sentence embeddings and save it."""
	texts, labels = get_training_data()

	embedder = _get_embedding_model()
	embeddings = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=True)

	X_train, X_test, y_train, y_test = train_test_split(
		embeddings,
		labels,
		test_size=TEST_SIZE,
		random_state=RANDOM_STATE,
		stratify=labels,
	)

	classifier = SVC(kernel="rbf", probability=True, random_state=RANDOM_STATE)
	classifier.fit(X_train, y_train)

	y_pred = classifier.predict(X_test)
	accuracy = accuracy_score(y_test, y_pred)
	print(f"Accuracy: {accuracy:.4f}")

	model_path.parent.mkdir(parents=True, exist_ok=True)
	with model_path.open("wb") as model_file:
		pickle.dump(classifier, model_file)
	print(f"Model saved to: {model_path}")

	global _intent_model
	_intent_model = classifier
	return classifier


def _load_intent_model(model_path: Path = MODEL_PATH) -> SVC:
	"""Load saved intent model from disk."""
	global _intent_model
	if _intent_model is None:
		if not model_path.exists():
			raise FileNotFoundError(
				f"Model not found at {model_path}. Run train_and_save_intent_model() first."
			)
		with model_path.open("rb") as model_file:
			_intent_model = pickle.load(model_file)
	return _intent_model


def classify_intent(email_text: str, model_path: Path = MODEL_PATH) -> Dict[str, str | float]:
	"""Classify email intent and return label + confidence percentage."""
	if not isinstance(email_text, str) or not email_text.strip():
		raise ValueError("email_text must be a non-empty string")

	embedder = _get_embedding_model()
	model = _load_intent_model(model_path)

	embedding = embedder.encode([email_text], convert_to_numpy=True, show_progress_bar=False)
	probabilities = model.predict_proba(embedding)[0]
	classes = model.classes_

	best_idx = int(np.argmax(probabilities))
	predicted_label = str(classes[best_idx])
	confidence_percentage = round(float(probabilities[best_idx]) * 100.0, 2)

	return {
		"intent": predicted_label,
		"confidence_percentage": confidence_percentage,
	}


if __name__ == "__main__":
	train_and_save_intent_model()

	sample_emails = {
		"meeting_request": "Can we schedule a meeting for tomorrow afternoon to discuss roadmap?",
		"complaint": "I am unhappy with the delayed response and unresolved issue.",
		"inquiry": "Could you share pricing details for your premium plan?",
		"follow_up": "Following up on my previous email about the pending approval.",
		"feedback": "The latest update is great and performance has improved.",
		"urgent": "Urgent: production checkout is failing for all users right now.",
		"general": "Please find attached the updated document for your reference.",
	}

	print("\nIntent classification test results:")
	for expected_intent, text in sample_emails.items():
		result = classify_intent(text)
		print(
			f"Expected: {expected_intent:16} | "
			f"Predicted: {result['intent']:16} | "
			f"Confidence: {result['confidence_percentage']:6.2f}%"
		)
