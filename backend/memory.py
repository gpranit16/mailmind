"""Email memory store and retrieval using persistent ChromaDB."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import List, Tuple

import chromadb


BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DB_PATH = BASE_DIR / "models" / "chroma_db"
COLLECTION_NAME = "email_memory"
EMBEDDING_DIM = 384

# Create persistent ChromaDB storage in MailMind/models/chroma_db
CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


def _is_duplicate_id_error(error: Exception) -> bool:
	"""Best-effort check for duplicate-id insertion errors."""
	message = str(error).lower()
	duplicate_markers = ("duplicate", "already exists", "unique", "existing id")
	return any(marker in message for marker in duplicate_markers)


def _id_exists(memory_id: str) -> bool:
	"""Check whether a Chroma record id already exists."""
	try:
		existing = _collection.get(ids=[memory_id], include=[])
		ids = existing.get("ids", [])
		return bool(ids)
	except Exception:
		return False


def _text_to_embedding(text: str) -> List[float]:
	"""Create deterministic local embeddings (fully offline).

	This avoids Chroma's default embedding-function download path.
	"""
	tokens = re.findall(r"\b\w+\b", str(text).lower())
	vector = [0.0] * EMBEDDING_DIM

	if not tokens:
		return vector

	for token in tokens:
		digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
		index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
		sign = 1.0 if digest[4] % 2 == 0 else -1.0
		vector[index] += sign

	norm = math.sqrt(sum(value * value for value in vector))
	if norm > 0:
		vector = [value / norm for value in vector]

	return vector


def store_memory(email_id: str, email_text: str, reply_text: str) -> None:
	"""Store email+reply as one document in ChromaDB.

	- Uses `email_id` as the Chroma id
	- Gracefully handles duplicate ids by upserting
	"""
	memory_id = str(email_id)
	email_text = str(email_text)
	reply_text = str(reply_text)

	combined_document = f"Email:\n{email_text}\n\nReply:\n{reply_text}"
	metadata = {"email_text": email_text, "reply_text": reply_text}
	embedding = _text_to_embedding(combined_document)

	# Handle duplicates gracefully by upserting when id already exists.
	if _id_exists(memory_id):
		_collection.upsert(
			ids=[memory_id],
			documents=[combined_document],
			metadatas=[metadata],
			embeddings=[embedding],
		)
		return

	try:
		_collection.add(
			ids=[memory_id],
			documents=[combined_document],
			metadatas=[metadata],
			embeddings=[embedding],
		)
	except Exception as exc:  # Graceful duplicate handling as requested.
		if _is_duplicate_id_error(exc):
			_collection.upsert(
				ids=[memory_id],
				documents=[combined_document],
				metadatas=[metadata],
				embeddings=[embedding],
			)
		else:
			raise


def retrieve_context(email_text: str, n_results: int = 3) -> List[Tuple[str, str]]:
	"""Retrieve top similar past email/reply pairs.

	Returns:
		List of tuples: [(past_email_text, past_reply_text), ...]
		Returns [] if no results are found.
	"""
	if not isinstance(email_text, str) or not email_text.strip():
		return []

	total_records = _collection.count()
	if total_records == 0:
		return []

	limit = max(1, min(int(n_results), total_records))
	query_embedding = _text_to_embedding(email_text)
	query_result = _collection.query(
		query_embeddings=[query_embedding],
		n_results=limit,
		include=["metadatas", "documents"],
	)

	metadatas = query_result.get("metadatas", [[]])
	documents = query_result.get("documents", [[]])

	if not metadatas or not metadatas[0]:
		return []

	context_pairs: List[Tuple[str, str]] = []
	for idx, metadata in enumerate(metadatas[0]):
		if isinstance(metadata, dict):
			past_email = str(metadata.get("email_text", "")).strip()
			past_reply = str(metadata.get("reply_text", "")).strip()

			if past_email or past_reply:
				context_pairs.append((past_email, past_reply))
				continue

		# Fallback parsing from combined document if metadata is missing.
		doc = ""
		if documents and documents[0] and idx < len(documents[0]):
			doc = str(documents[0][idx])

		if "Reply:" in doc:
			before_reply, after_reply = doc.split("Reply:", 1)
			parsed_email = before_reply.replace("Email:", "").strip()
			parsed_reply = after_reply.strip()
			context_pairs.append((parsed_email, parsed_reply))

	return context_pairs


def clear_memory() -> None:
	"""Delete all stored memory and recreate the collection."""
	global _collection
	try:
		_client.delete_collection(name=COLLECTION_NAME)
	except Exception:
		# If collection does not exist or cannot be deleted, continue by recreating.
		pass
	_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


if __name__ == "__main__":
	# Store 3 sample email-reply pairs.
	store_memory(
		"email_1",
		"Can we schedule a meeting for tomorrow afternoon to review project status?",
		"Absolutely. I am available at 3 PM tomorrow for the meeting.",
	)
	store_memory(
		"email_2",
		"I am unhappy with the delayed shipment and need an update.",
		"Sorry for the delay. Your shipment is now prioritized and will arrive tomorrow.",
	)
	store_memory(
		"email_3",
		"Could you share pricing details for the enterprise plan?",
		"Sure, I have attached enterprise pricing and feature details for your review.",
	)

	# Retrieve context for a new similar email.
	new_email_text = "Can we have a quick call tomorrow to discuss the project timeline?"
	retrieved = retrieve_context(new_email_text, n_results=3)

	print("Retrieved context results:")
	if not retrieved:
		print("No similar past email/reply pairs found.")
	else:
		for index, (past_email, past_reply) in enumerate(retrieved, start=1):
			print(f"\nResult {index}:")
			print(f"Past Email: {past_email}")
			print(f"Past Reply: {past_reply}")
