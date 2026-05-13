import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from spam_detector import predict as detect_spam
from sentiment import analyze_sentiment
from intent_classifier import classify_intent
from confidence import decide_action, get_action_message
from calendar_agent import (
	check_calendar_availability,
	create_calendar_event,
	list_upcoming_events,
	parse_meeting_window,
)
from memory import clear_memory as clear_vector_memory
from memory import retrieve_context, store_memory
from reply_generator import generate_reply
from gmail_agent import (
	fetch_unread_emails,
	get_calendar_service,
	get_gmail_service,
	mark_email_as_read,
	send_reply,
)


BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "models"
HISTORY_PATH = MODELS_DIR / "email_history.json"

MODELS_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="MailMind API")

# Allow all origins for development/testing.
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


# Analytics counters
emails_processed = 0
spam_blocked = 0
auto_replied = 0
flagged_review = 0
PROCESS_LOCK = Lock()


def _load_history() -> list[dict]:
	"""Load persisted email history from disk."""
	if not HISTORY_PATH.exists():
		return []

	try:
		with HISTORY_PATH.open("r", encoding="utf-8") as history_file:
			data = json.load(history_file)
		return data if isinstance(data, list) else []
	except Exception:
		return []


def _save_history() -> None:
	"""Persist email history to disk."""
	with HISTORY_PATH.open("w", encoding="utf-8") as history_file:
		json.dump(email_history, history_file, ensure_ascii=False, indent=2)


def _upsert_history_item(item: dict) -> None:
	"""Insert/update one history item by id and persist."""
	item_id = str(item.get("id", "")).strip()

	if item_id:
		for index, existing in enumerate(email_history):
			if str(existing.get("id", "")).strip() == item_id:
				email_history[index] = item
				_save_history()
				return

	email_history.append(item)
	_save_history()


email_history = _load_history()


def _extract_recipient_email(sender_value: str) -> str:
	"""Extract email address from sender header value."""
	if not sender_value:
		return ""

	match = re.search(r"<([^>]+)>", sender_value)
	if match:
		return match.group(1).strip()

	# Fallback: if sender itself looks like an email, return as-is.
	if "@" in sender_value:
		return sender_value.strip()

	return ""


def _extract_sender_name(sender_value: str) -> str:
	"""Extract a readable sender name from header value."""
	if not sender_value:
		return "there"

	match = re.search(r"^(.*?)<[^>]+>$", sender_value)
	if match and match.group(1).strip():
		return match.group(1).strip()

	sender_value = sender_value.strip()
	if "@" in sender_value and " " not in sender_value:
		return sender_value.split("@", 1)[0]

	return sender_value


def _find_history_item(email_id: str) -> dict | None:
	"""Find most recent history item by email id."""
	normalized_id = str(email_id or "").strip()
	if not normalized_id:
		return None

	for item in reversed(email_history):
		if str(item.get("id", "")).strip() == normalized_id:
			return item

	return None


def _preprocess_email_body(body_text: str) -> str:
	"""Preprocess raw email text to improve classification/reply quality."""
	if not body_text:
		return ""

	stop_markers = (
		"-----original message-----",
		"forwarded message",
		"from:",
		"sent:",
		"subject:",
	)

	cleaned_lines = []
	for line in str(body_text).splitlines():
		stripped = line.strip()
		lowered = stripped.lower()

		if stripped.startswith(">"):
			continue

		if re.match(r"^on .+ wrote:$", lowered):
			break

		if any(marker in lowered for marker in stop_markers):
			break

		cleaned_lines.append(stripped)

	cleaned = " ".join(" ".join(cleaned_lines).split())
	return cleaned[:12000]


def _build_meeting_busy_reply(sender_name: str, requested_slot: str | None) -> str:
	"""Deterministic meeting reply when requested slot is busy."""
	slot_text = requested_slot or "the requested time"
	return (
		f"Hi {sender_name},\n\n"
		f"Thank you for your meeting request. I checked the calendar and {slot_text} is not available. "
		"Could you please share 2-3 alternative time slots? "
		"I will confirm one of them as soon as I receive your options.\n\n"
		"Best regards"
	)


def _build_meeting_unparsed_reply(sender_name: str) -> str:
	"""Deterministic meeting reply when date/time cannot be parsed."""
	return (
		f"Hi {sender_name},\n\n"
		"Thank you for your meeting request. I could not identify a clear date and time from your email. "
		"Please share one specific date and time (including timezone), or 2-3 possible slots, and I will confirm quickly.\n\n"
		"Best regards"
	)


@app.post("/process-emails")
def process_emails():
	global emails_processed, spam_blocked, auto_replied, flagged_review

	with PROCESS_LOCK:
		results = []
		gmail_service = get_gmail_service()
		try:
			calendar_service = get_calendar_service()
		except Exception:
			calendar_service = None

		unread_emails = fetch_unread_emails(10, service=gmail_service)

		for email_item in unread_emails:
			email_id = email_item.get("id", "")
			sender = email_item.get("sender", "")
			subject = email_item.get("subject", "")
			raw_body = email_item.get("body", "")
			body = _preprocess_email_body(raw_body) or raw_body
			processed_at = datetime.now(timezone.utc).isoformat()

			existing_item = _find_history_item(email_id)
			if existing_item and (
				bool(existing_item.get("reply_sent"))
				or str(existing_item.get("status", "")).lower() in {"processed", "spam"}
			):
				mark_email_as_read(gmail_service, email_id)
				results.append(
					{
						"id": email_id,
						"sender": sender,
						"subject": subject,
						"status": "skipped_duplicate",
						"processed_at": processed_at,
					}
				)
				continue

			try:
				# a. Spam check
				spam_result = detect_spam(body)
				is_spam = bool(spam_result.get("is_spam", False))

				# b. If spam, increment and continue
				if is_spam:
					spam_blocked += 1
					history_item = {
						"id": email_id,
						"sender": sender,
						"subject": subject,
						"status": "spam",
						"spam": spam_result,
						"processed_at": processed_at,
					}
					results.append(history_item)
					_upsert_history_item(history_item)
					mark_email_as_read(gmail_service, email_id)
					continue

				# c. Sentiment analysis
				sentiment_label, sentiment_score = analyze_sentiment(body)

				# d. Intent classification
				intent_result = classify_intent(body)
				intent_label = intent_result.get("intent", "general")
				intent_confidence = float(intent_result.get("confidence_percentage", 0.0))

				# e. Retrieve similar past context
				context = retrieve_context(body, n_results=3)

				# f. Decide action based on intent confidence (calendar will guide reply behavior)
				action = decide_action(intent_confidence)
				action_message = get_action_message(action)

				meeting_status = {
					"checked": False,
					"available": None,
					"reason": "Not a meeting request",
				}
				calendar_event = None
				availability_note = ""

				if intent_label == "meeting_request":
					meeting_status["checked"] = True
					parsed_window = parse_meeting_window(body)

					if parsed_window.get("status") == "parsed":
						if calendar_service is None:
							meeting_status = {
								"checked": True,
								"available": None,
								"display": parsed_window.get("display"),
								"reason": "Calendar service unavailable",
							}
							availability_note = (
								"Calendar check unavailable. Do not confirm slot; ask sender for alternatives."
							)
							if action == "auto_send":
								action = "flag_review"
								action_message = "Calendar unavailable. Flagged for manual review."
						else:
							try:
								is_available, busy_slots = check_calendar_availability(
									calendar_service,
									parsed_window["start_iso"],
									parsed_window["end_iso"],
								)
							except Exception as calendar_check_error:
								meeting_status = {
									"checked": True,
									"available": None,
									"display": parsed_window.get("display"),
									"reason": f"Calendar check failed: {calendar_check_error}",
								}
								availability_note = (
									"Calendar check failed. Do not confirm slot; ask sender for alternatives."
								)
								if action == "auto_send":
									action = "flag_review"
									action_message = "Calendar check failed. Flagged for manual review."
							else:
								meeting_status = {
									"checked": True,
									"available": bool(is_available),
									"display": parsed_window.get("display"),
									"start_iso": parsed_window.get("start_iso"),
									"end_iso": parsed_window.get("end_iso"),
									"timezone": parsed_window.get("timezone"),
									"busy_slots": busy_slots,
								}

								if is_available:
									availability_note = (
										f"Calendar check: requested slot {parsed_window.get('display')} is free. "
										"You may confirm this slot confidently."
									)
								else:
									availability_note = (
										f"Calendar check: requested slot {parsed_window.get('display')} is busy. "
										"Do not confirm this exact slot. Ask for alternate times."
									)
					else:
						meeting_status = {
							"checked": True,
							"available": None,
							"reason": parsed_window.get("reason", "Could not parse meeting date/time"),
						}
						availability_note = (
							"Calendar check: unable to parse exact date/time from this email. "
							"Ask sender to confirm a specific date and time before booking."
						)

				sender_name = _extract_sender_name(sender)

				# g. Generate reply
				if intent_label == "meeting_request" and action == "auto_send":
					if meeting_status.get("available") is False:
						reply_text = _build_meeting_busy_reply(
							sender_name=sender_name,
							requested_slot=meeting_status.get("display"),
						)
					elif meeting_status.get("available") is None:
						reply_text = _build_meeting_unparsed_reply(sender_name=sender_name)
					else:
						reply_text = generate_reply(
							email_text=body,
							sender_name=sender_name,
							sentiment=sentiment_label,
							intent=intent_label,
							context=context,
							availability_note=availability_note,
						)
				else:
					reply_text = generate_reply(
						email_text=body,
						sender_name=sender_name,
						sentiment=sentiment_label,
						intent=intent_label,
						context=context,
						availability_note=availability_note,
					)

				reply_sent = False
				recipient_email = _extract_recipient_email(sender)

				# h. Auto-send flow
				if action == "auto_send":
					reply_sent = send_reply(
						service=gmail_service,
						email_id=email_id,
						reply_text=reply_text,
						recipient_email=recipient_email,
						subject=subject,
					)

					if reply_sent:
						store_memory(email_id, body, reply_text)
						auto_replied += 1

						if (
							intent_label == "meeting_request"
							and meeting_status.get("available") is True
							and calendar_service is not None
						):
							try:
								summary = f"Meeting: {subject or 'MailMind Scheduled Meeting'}"
								description = (
									f"Auto-created by MailMind from email ID {email_id}.\n\n"
									f"Original subject: {subject}\n"
									f"Sender: {sender}\n"
								)
								calendar_event = create_calendar_event(
									calendar_service=calendar_service,
									summary=summary,
									description=description,
									start_iso=meeting_status.get("start_iso"),
									end_iso=meeting_status.get("end_iso"),
									attendee_emails=[recipient_email] if recipient_email else [],
								)
							except Exception as calendar_error:
								calendar_event = {
									"error": str(calendar_error),
								}
					else:
						action = "flag_review"
						action_message = "Auto-send failed. Flagged for manual review."
						flagged_review += 1
				elif action == "flag_review":
					flagged_review += 1

				# i. Increment processed counter (for non-spam)
				emails_processed += 1

				# j. Add full result
				history_item = {
					"id": email_id,
					"sender": sender,
					"subject": subject,
					"status": "processed",
					"spam": spam_result,
					"sentiment": {
						"label": sentiment_label,
						"compound": sentiment_score,
					},
					"intent": intent_result,
					"context": context,
					"reply": reply_text,
					"action": action,
					"action_message": action_message,
					"reply_sent": reply_sent,
					"meeting_status": meeting_status,
					"calendar_event": calendar_event,
					"processed_at": processed_at,
				}
				results.append(history_item)
				_upsert_history_item(history_item)
				mark_email_as_read(gmail_service, email_id)
			except Exception as exc:
				error_item = {
					"id": email_id,
					"sender": sender,
					"subject": subject,
					"status": "error",
					"error": str(exc),
					"processed_at": processed_at,
				}
				results.append(error_item)
				_upsert_history_item(error_item)
				mark_email_as_read(gmail_service, email_id)

		return results


@app.get("/history")
def get_history(limit: int = 200):
	"""Return persisted processing history (most recent first)."""
	safe_limit = max(1, min(int(limit), 1000))
	return list(reversed(email_history))[:safe_limit]


@app.get("/calendar/meetings")
def get_calendar_meetings(limit: int = 200, upcoming: int = 20):
	"""Return processed meeting requests + upcoming Google Calendar events."""
	safe_limit = max(1, min(int(limit), 1000))
	safe_upcoming = max(1, min(int(upcoming), 100))

	processed_meetings = []
	for item in reversed(email_history):
		if len(processed_meetings) >= safe_limit:
			break

		intent = (item.get("intent") or {}).get("intent")
		meeting_status = item.get("meeting_status") or {}
		if intent != "meeting_request" and not meeting_status.get("checked"):
			continue

		processed_meetings.append(
			{
				"id": item.get("id"),
				"sender": item.get("sender"),
				"subject": item.get("subject"),
				"status": item.get("status"),
				"action": item.get("action"),
				"reply_sent": item.get("reply_sent"),
				"processed_at": item.get("processed_at"),
				"meeting_status": meeting_status,
				"calendar_event": item.get("calendar_event"),
				"reply": item.get("reply"),
			}
		)

	upcoming_events = []
	calendar_error = None
	try:
		calendar_service = get_calendar_service()
		upcoming_events = list_upcoming_events(calendar_service, max_results=safe_upcoming)
	except Exception as exc:
		calendar_error = str(exc)

	return {
		"processed_meetings": processed_meetings,
		"upcoming_events": upcoming_events,
		"calendar_error": calendar_error,
	}


@app.post("/history/clear")
def clear_history():
	"""Clear persisted processing history."""
	email_history.clear()
	_save_history()
	return {"status": "ok", "message": "History cleared"}


@app.post("/clear-memory")
def clear_memory_endpoint():
	"""Clear vector memory store."""
	clear_vector_memory()
	return {"status": "ok", "message": "Vector memory cleared"}


@app.post("/reset-analytics")
def reset_analytics():
	"""Reset runtime analytics counters."""
	global emails_processed, spam_blocked, auto_replied, flagged_review

	emails_processed = 0
	spam_blocked = 0
	auto_replied = 0
	flagged_review = 0

	return {"status": "ok", "message": "Analytics reset"}


@app.get("/analytics")
def get_analytics():
	return {
		"emails_processed": emails_processed,
		"spam_blocked": spam_blocked,
		"auto_replied": auto_replied,
		"flagged_review": flagged_review,
	}


@app.get("/health")
def health_check():
	return {"status": "ok"}


if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
