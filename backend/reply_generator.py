"""Professional email reply generation with Gemini + Groq fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import google.generativeai as genai
from dotenv import load_dotenv


# Load env from backend/.env first, then project-root .env (without overriding).
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(dotenv_path=BACKEND_DIR / ".env")
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
GROQ_MODELS = os.getenv("GROQ_MODELS", "").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()  # auto|gemini|groq

_gemini_model = None

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
	genai.configure(api_key=GEMINI_API_KEY)
	_gemini_model = genai.GenerativeModel(GEMINI_MODEL)


def _format_context(context: Iterable) -> str:
	"""Format past context list for prompt injection."""
	if not context:
		return "No relevant past context available."

	formatted = []
	for idx, item in enumerate(context, start=1):
		if idx > 5:
			break
		if isinstance(item, tuple) and len(item) >= 2:
			past_email, past_reply = item[0], item[1]
			formatted.append(
				f"Context {idx}:\nPast Email: {past_email}\nPast Reply: {past_reply}"
			)
		elif isinstance(item, dict):
			past_email = item.get("email") or item.get("email_text") or ""
			past_reply = item.get("reply") or item.get("reply_text") or ""
			formatted.append(
				f"Context {idx}:\nPast Email: {past_email}\nPast Reply: {past_reply}"
			)
		else:
			formatted.append(f"Context {idx}: {item}")

	return "\n\n".join(formatted) if formatted else "No relevant past context available."


def _provider_sequence() -> list[str]:
	"""Return LLM provider order based on LLM_PROVIDER env."""
	if LLM_PROVIDER == "gemini":
		return ["gemini", "groq"]
	if LLM_PROVIDER == "groq":
		return ["groq", "gemini"]
	return ["gemini", "groq"]


def _groq_model_candidates() -> list[str]:
	"""Return Groq model candidates prioritized for free-tier availability."""
	models = []
	if GROQ_MODELS:
		models.extend([m.strip() for m in GROQ_MODELS.split(",") if m.strip()])

	# Keep user-selected model first.
	if GROQ_MODEL:
		models.insert(0, GROQ_MODEL)

	# Common free-tier/chat-capable fallbacks.
	models.extend([
		"llama-3.1-8b-instant",
		"llama3-8b-8192",
		"gemma2-9b-it",
	])

	# De-duplicate preserving order.
	seen = set()
	ordered = []
	for model in models:
		if model not in seen:
			seen.add(model)
			ordered.append(model)
	return ordered


def _generate_with_gemini(prompt: str) -> str:
	"""Generate text with Gemini."""
	if _gemini_model is None:
		raise RuntimeError("Gemini is not configured")

	response = _gemini_model.generate_content(prompt)
	generated_text = (getattr(response, "text", "") or "").strip()
	if not generated_text:
		raise RuntimeError("Gemini returned an empty response")

	return generated_text


def _generate_with_groq(prompt: str) -> str:
	"""Generate text with Groq chat completions API."""
	if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
		raise RuntimeError("Groq is not configured")

	errors = []
	for groq_model in _groq_model_candidates():
		payload = {
			"model": groq_model,
			"messages": [
				{"role": "system", "content": "You are a professional email assistant."},
				{"role": "user", "content": prompt},
			],
			"temperature": 0.3,
			"max_tokens": 350,
		}

		req = Request(
			url="https://api.groq.com/openai/v1/chat/completions",
			data=json.dumps(payload).encode("utf-8"),
			headers={
				"Authorization": f"Bearer {GROQ_API_KEY}",
				"Content-Type": "application/json",
			},
			method="POST",
		)

		try:
			with urlopen(req, timeout=60) as response:
				body = response.read().decode("utf-8")
		except HTTPError as exc:
			error_text = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
			errors.append(f"{groq_model}: {error_text or str(exc)}")
			continue
		except URLError as exc:
			errors.append(f"{groq_model}: connection error {exc}")
			continue

		data = json.loads(body)
		choices = data.get("choices", [])
		if not choices:
			errors.append(f"{groq_model}: no choices")
			continue

		message = choices[0].get("message", {})
		generated_text = str(message.get("content", "")).strip()
		if not generated_text:
			errors.append(f"{groq_model}: empty content")
			continue

		return generated_text

	raise RuntimeError(f"Groq request failed for all models. Details: {' | '.join(errors)}")


def _fallback_template_reply(sender_name: str, intent: str) -> str:
	"""Generate a deterministic fallback reply if all LLM providers fail."""
	name = sender_name or "there"

	if intent == "meeting_request":
		return (
			f"Hi {name},\n\n"
			"Thank you for your meeting request. I have received your message and will confirm "
			"a suitable time shortly after reviewing the calendar details.\n\n"
			"Best regards"
		)

	if intent == "complaint":
		return (
			f"Hi {name},\n\n"
			"Thank you for raising this issue. I am sorry for the inconvenience. "
			"We have noted your concern and will share an update as soon as possible.\n\n"
			"Best regards"
		)

	return (
		f"Hi {name},\n\n"
		"Thank you for your email. I have received your message and will get back to you shortly "
		"with the required details.\n\n"
		"Best regards"
	)


def generate_reply(
	email_text: str,
	sender_name: str,
	sentiment: str,
	intent: str,
	context,
	availability_note: str = "",
) -> str:
	"""Generate a professional, concise reply (max 150 words)."""
	if not isinstance(email_text, str) or not email_text.strip():
		raise ValueError("email_text must be a non-empty string")

	sender_name = str(sender_name or "Sender")
	sentiment = str(sentiment or "neutral").strip().lower()
	intent = str(intent or "general").strip().lower()
	context_text = _format_context(context)

	tone_instructions = {
		"positive": "Use a friendly and appreciative tone.",
		"negative": "Use an apologetic, calm, and solution-oriented tone.",
		"neutral": "Use a professional and clear tone.",
	}

	intent_instructions = {
		"meeting_request": "Propose or confirm a suitable schedule and next steps.",
		"complaint": "Acknowledge the issue, apologize, and provide a resolution path.",
		"inquiry": "Provide clear and relevant information to answer the question.",
		"follow_up": "Share a concrete update and expected timeline.",
		"urgent": "Respond immediately with priority and actionable next steps.",
		"feedback": "Thank them for feedback and mention how it will be addressed.",
		"general": "Provide a clear, professional response appropriate to the message.",
	}

	tone_rule = tone_instructions.get(sentiment, tone_instructions["neutral"])
	intent_rule = intent_instructions.get(intent, intent_instructions["general"])
	availability_note = str(availability_note or "").strip()

	prompt = f"""
You are a professional email assistant.

Sender Name: {sender_name}
Detected Sentiment: {sentiment}
Detected Intent: {intent}

Tone Guidance:
- If sentiment is positive, be friendly.
- If sentiment is negative, be apologetic.
- If sentiment is neutral, be professional.
- Apply this specifically now: {tone_rule}

Intent Guidance:
- meeting_request: schedule it
- complaint: apologize and resolve
- inquiry: provide information
- follow_up: give update
- urgent: respond immediately
- Apply this specifically now: {intent_rule}

Past Context (if available):
{context_text}

Calendar Availability Guidance (if provided):
{availability_note or "No calendar guidance provided."}

Incoming Email:
{email_text}

Write a professional, concise reply email.
Maximum length: 150 words.
Do not include placeholders like [Your Name].
""".strip()

	errors = []
	for provider in _provider_sequence():
		try:
			if provider == "gemini":
				return _generate_with_gemini(prompt)
			if provider == "groq":
				return _generate_with_groq(prompt)
		except Exception as exc:
			errors.append(f"{provider}: {exc}")

	fallback = _fallback_template_reply(sender_name=sender_name, intent=intent)
	return (
		f"{fallback}\n\n"
		"[Note: AI provider unavailable during this run; generated fallback response.]"
	)


if __name__ == "__main__":
	sample_email = (
		"Hi team, I am disappointed because my issue has been pending for days and I "
		"still have not received a proper fix. Please resolve this as soon as possible."
	)

	sample_context = [
		(
			"I reported a login problem last week and did not hear back.",
			"Sorry for the delay. We escalated your case and will update you within 24 hours.",
		)
	]

	try:
		reply = generate_reply(
			email_text=sample_email,
			sender_name="Alex",
			sentiment="negative",
			intent="complaint",
			context=sample_context,
		)
		print("Generated Reply:\n")
		print(reply)
	except Exception as exc:
		print(f"Error generating reply: {exc}")
