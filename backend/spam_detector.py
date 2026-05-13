"""Spam detection training and inference using sentence-transformers + XGBoost.

This module:
1) Loads `models/emails.csv`
2) Uses `Prediction` as label column (1=spam, 0=ham)
3) Converts each feature row into text by joining feature names with value > 0
4) Builds sentence embeddings using `all-MiniLM-L6-v2`
5) Trains an XGBoost classifier on embeddings
6) Prints accuracy, precision, recall, and F1 score
7) Saves model to `models/spam_model.pkl`
8) Exposes `predict(email_text)` for runtime inference
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "models"
DATA_PATH = MODELS_DIR / "emails.csv"
MODEL_PATH = MODELS_DIR / "spam_model.pkl"

LABEL_COLUMN = "Prediction"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TEST_SIZE = 0.2
RANDOM_STATE = 42

_embedding_model: SentenceTransformer | None = None
_classifier_model: XGBClassifier | None = None


def _get_embedding_model() -> SentenceTransformer:
	"""Lazily load and cache the sentence-transformer model."""
	global _embedding_model
	if _embedding_model is None:
		_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
	return _embedding_model


def _row_to_text_tokens(feature_row: pd.Series) -> str:
	"""Join column names where the row value is greater than 0."""
	active_columns = feature_row.index[feature_row.values > 0]
	return " ".join(active_columns)


def load_training_data(csv_path: Path = DATA_PATH) -> tuple[list[str], np.ndarray]:
	"""Load CSV and convert rows into text + label arrays."""
	if not csv_path.exists():
		raise FileNotFoundError(f"Dataset not found: {csv_path}")

	df = pd.read_csv(csv_path)

	if LABEL_COLUMN not in df.columns:
		raise ValueError(f"Expected label column '{LABEL_COLUMN}' in CSV.")

	labels = pd.to_numeric(df[LABEL_COLUMN], errors="coerce").fillna(0).astype(int).to_numpy()

	# Exclude label, convert remaining columns to numeric, and treat non-numeric as 0.
	feature_df = df.drop(columns=[LABEL_COLUMN]).apply(pd.to_numeric, errors="coerce").fillna(0)
	texts = feature_df.apply(_row_to_text_tokens, axis=1).tolist()

	return texts, labels


def train_and_save_model(
	csv_path: Path = DATA_PATH,
	model_path: Path = MODEL_PATH,
) -> XGBClassifier:
	"""Train XGBoost on sentence embeddings and save model to disk."""
	texts, labels = load_training_data(csv_path)

	embedding_model = _get_embedding_model()
	embeddings = embedding_model.encode(
		texts,
		convert_to_numpy=True,
		show_progress_bar=True,
	)

	X_train, X_test, y_train, y_test = train_test_split(
		embeddings,
		labels,
		test_size=TEST_SIZE,
		random_state=RANDOM_STATE,
		stratify=labels,
	)

	classifier = XGBClassifier(
		n_estimators=300,
		max_depth=6,
		learning_rate=0.05,
		subsample=0.9,
		colsample_bytree=0.9,
		objective="binary:logistic",
		eval_metric="logloss",
		random_state=RANDOM_STATE,
		n_jobs=-1,
	)
	classifier.fit(X_train, y_train)

	y_pred = classifier.predict(X_test)
	print(f"Accuracy : {accuracy_score(y_test, y_pred):.4f}")
	print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
	print(f"Recall   : {recall_score(y_test, y_pred, zero_division=0):.4f}")
	print(f"F1 Score : {f1_score(y_test, y_pred, zero_division=0):.4f}")

	model_path.parent.mkdir(parents=True, exist_ok=True)
	with model_path.open("wb") as model_file:
		pickle.dump(classifier, model_file)

	print(f"Model saved to: {model_path}")

	global _classifier_model
	_classifier_model = classifier
	return classifier


def _load_classifier(model_path: Path = MODEL_PATH) -> XGBClassifier:
	"""Load and cache the saved XGBoost model."""
	global _classifier_model
	if _classifier_model is None:
		if not model_path.exists():
			raise FileNotFoundError(
				f"Saved model not found at {model_path}. "
				"Run train_and_save_model() first."
			)
		with model_path.open("rb") as model_file:
			_classifier_model = pickle.load(model_file)
	return _classifier_model


def predict(email_text: str, model_path: Path = MODEL_PATH) -> Dict[str, float | bool]:
	"""Predict spam/ham for raw email text.

	Returns:
		{
			"is_spam": bool,
			"confidence_percentage": float
		}
	"""
	if not isinstance(email_text, str) or not email_text.strip():
		raise ValueError("email_text must be a non-empty string.")

	embedding_model = _get_embedding_model()
	classifier = _load_classifier(model_path)

	embedding = embedding_model.encode(
		[email_text],
		convert_to_numpy=True,
		show_progress_bar=False,
	)

	spam_probability = float(classifier.predict_proba(embedding)[0][1])
	is_spam = spam_probability >= 0.5

	# Confidence of predicted class.
	confidence = spam_probability if is_spam else (1.0 - spam_probability)

	return {
		"is_spam": bool(is_spam),
		"confidence_percentage": round(confidence * 100, 2),
	}


if __name__ == "__main__":
	train_and_save_model()
