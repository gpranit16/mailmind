import os
import base64
from typing import Optional
from threading import RLock
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


SCOPES = [
	"https://www.googleapis.com/auth/gmail.modify",
	"https://www.googleapis.com/auth/calendar",
]

# Folder where this file exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_LOCK = RLock()
_CACHED_CREDS: Optional[Credentials] = None
_CACHED_GMAIL_SERVICE = None
_CACHED_CALENDAR_SERVICE = None


def _run_oauth_flow(credentials_path: str) -> Credentials:
	"""Run OAuth flow with localhost callback, then fallback to manual URL paste.

	Fallback helps when localhost redirect cannot connect in browser.
	"""
	# First try local callback server (normal desktop flow).
	try:
		flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
		return flow.run_local_server(
			host="127.0.0.1",
			port=0,
			open_browser=True,
			authorization_prompt_message="Please visit this URL to authorize this application: {url}",
			success_message="Authorization complete. You may close this tab.",
		)
	except KeyboardInterrupt as exc:
		# User cancelled local-server flow; continue to manual fallback.
		print("\nLocal OAuth callback interrupted. Switching to manual auth fallback...")
		_last_error = exc
	except Exception as exc:
		print(f"\nLocal OAuth callback failed ({exc}). Switching to manual auth fallback...")
		_last_error = exc

	# Manual fallback: user copies redirect URL from browser address bar.
	flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
	auth_url, _ = flow.authorization_url(
		prompt="consent",
		access_type="offline",
		include_granted_scopes="true",
	)

	print("\nManual OAuth fallback:")
	print("1) Open this URL in your browser and grant access:")
	print(auth_url)
	print("2) After consent, your browser may show localhost connection error.")
	print("3) Copy the FULL URL from the browser address bar and paste it here.")
	authorization_response = input("Paste full redirect URL: ").strip()

	if not authorization_response:
		raise RuntimeError("No redirect URL provided for manual OAuth flow") from _last_error

	flow.fetch_token(authorization_response=authorization_response)
	return flow.credentials


def get_gmail_service():
	"""Authenticate and return a Gmail API service instance."""
	global _CACHED_GMAIL_SERVICE

	with _CACHE_LOCK:
		if _CACHED_GMAIL_SERVICE is not None:
			return _CACHED_GMAIL_SERVICE

		creds = get_google_credentials()
		_CACHED_GMAIL_SERVICE = build("gmail", "v1", credentials=creds)
		return _CACHED_GMAIL_SERVICE


def _ensure_valid_credentials(creds: Optional[Credentials]) -> Optional[Credentials]:
	"""Refresh or invalidate credentials depending on token/scope validity."""
	if creds is None:
		return None

	try:
		if not creds.has_scopes(SCOPES):
			return None
	except Exception:
		return None

	if creds.valid:
		return creds

	if creds.expired and creds.refresh_token:
		try:
			creds.refresh(Request())
			return creds
		except Exception:
			return None

	return None


def get_google_credentials() -> Credentials:
	"""Authenticate and return reusable Google OAuth credentials."""
	global _CACHED_CREDS, _CACHED_GMAIL_SERVICE, _CACHED_CALENDAR_SERVICE

	with _CACHE_LOCK:
		token_path = os.path.join(BASE_DIR, "token.json")
		credentials_path = os.path.join(BASE_DIR, "credentials.json")

		cached = _ensure_valid_credentials(_CACHED_CREDS)
		if cached is not None:
			_CACHED_CREDS = cached
			return _CACHED_CREDS

		creds: Optional[Credentials] = None
		if os.path.exists(token_path):
			try:
				creds = Credentials.from_authorized_user_file(token_path, SCOPES)
			except Exception:
				creds = None

		creds = _ensure_valid_credentials(creds)
		if creds is None:
			creds = _run_oauth_flow(credentials_path)

		with open(token_path, "w", encoding="utf-8") as token_file:
			token_file.write(creds.to_json())

		_CACHED_CREDS = creds
		_CACHED_GMAIL_SERVICE = None
		_CACHED_CALENDAR_SERVICE = None
		return _CACHED_CREDS


def get_calendar_service():
	"""Authenticate and return a Google Calendar API service instance."""
	global _CACHED_CALENDAR_SERVICE

	with _CACHE_LOCK:
		if _CACHED_CALENDAR_SERVICE is not None:
			return _CACHED_CALENDAR_SERVICE

		creds = get_google_credentials()
		_CACHED_CALENDAR_SERVICE = build("calendar", "v3", credentials=creds)
		return _CACHED_CALENDAR_SERVICE


def _decode_base64_data(data: str) -> str:
	"""Decode Gmail URL-safe base64 body content."""
	if not data:
		return ""

	try:
		padding = "=" * (-len(data) % 4)
		decoded_bytes = base64.urlsafe_b64decode(data + padding)
		return decoded_bytes.decode("utf-8", errors="ignore")
	except Exception:
		return ""


def _extract_body(payload: dict) -> str:
	"""Extract message body from Gmail payload structure."""
	if not payload:
		return ""

	body_data = payload.get("body", {}).get("data")
	if body_data:
		return _decode_base64_data(body_data)

	parts = payload.get("parts", [])
	if not parts:
		return ""

	# Prefer text/plain first.
	for part in parts:
		mime_type = part.get("mimeType", "")
		if mime_type == "text/plain":
			data = part.get("body", {}).get("data")
			if data:
				return _decode_base64_data(data)

	# Then fallback to text/html.
	for part in parts:
		mime_type = part.get("mimeType", "")
		if mime_type == "text/html":
			data = part.get("body", {}).get("data")
			if data:
				return _decode_base64_data(data)

	# Recursive fallback for nested parts.
	for part in parts:
		nested_body = _extract_body(part)
		if nested_body:
			return nested_body

	return ""


def fetch_unread_emails(max_results=10, service=None):
	"""Fetch unread inbox emails and return id/sender/subject/body."""
	service = service or get_gmail_service()

	response = (
		service.users()
		.messages()
		.list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
		.execute()
	)

	messages = response.get("messages", [])
	email_list = []

	for message in messages:
		message_id = message.get("id")
		full_message = (
			service.users().messages().get(userId="me", id=message_id, format="full").execute()
		)

		payload = full_message.get("payload", {})
		headers = payload.get("headers", [])

		sender = ""
		subject = ""
		for header in headers:
			name = (header.get("name") or "").lower()
			value = header.get("value", "")
			if name == "from":
				sender = value
			elif name == "subject":
				subject = value

		body = _extract_body(payload)

		email_list.append(
			{
				"id": message_id,
				"sender": sender,
				"subject": subject,
				"body": body,
			}
		)

	return email_list


def mark_email_as_read(service, email_id: str) -> bool:
	"""Remove UNREAD label from an email so it won't be reprocessed repeatedly."""
	if not email_id:
		return False

	try:
		(
			service.users()
			.messages()
			.modify(
				userId="me",
				id=email_id,
				body={"removeLabelIds": ["UNREAD"]},
			)
			.execute()
		)
		return True
	except Exception:
		return False


def send_reply(service, email_id, reply_text, recipient_email, subject):
	"""Send a reply email using Gmail API and return success status."""
	try:
		message = MIMEText(reply_text)
		message["To"] = recipient_email

		clean_subject = subject or ""
		if clean_subject.lower().startswith("re:"):
			message["Subject"] = clean_subject
		else:
			message["Subject"] = f"Re: {clean_subject}" if clean_subject else "Re:"

		raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

		send_body = {"raw": raw_message}

		if email_id:
			original_message = (
				service.users()
				.messages()
				.get(userId="me", id=email_id, format="metadata")
				.execute()
			)
			thread_id = original_message.get("threadId")
			if thread_id:
				send_body["threadId"] = thread_id

		(
			service.users()
			.messages()
			.send(userId="me", body=send_body)
			.execute()
		)

		return True
	except Exception:
		return False


if __name__ == "__main__":
	unread_emails = fetch_unread_emails(max_results=10)
	print(f"Unread emails found: {len(unread_emails)}")

	if unread_emails:
		first_email = unread_emails[0]
		print(f"First email subject: {first_email.get('subject', '')}")
		print(f"First email sender: {first_email.get('sender', '')}")
