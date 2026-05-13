# MailMind - Start to Finish Usage Guide

This guide explains setup, login behavior, run order, and daily usage.

## 1) One-time setup

### Prerequisites
- Python 3.12+
- Node.js + npm
- Gmail API credentials file at:
  - `backend/credentials.json`
- LLM keys in `.env` (Gemini and/or Groq)

### Recommended folders
- Backend: `Mailmind/backend`
- Frontend: `Mailmind/frontend`
- Python env: `Mailmind/venv`

---

## 2) First run (exact order)

1. **Open Terminal 1 (PowerShell) from project root**
  - Path should be: `C:\Users\gupta\OneDrive\Desktop\Mailmind`
2. **Start backend**
  - `Set-Location .\backend`
  - `c:/Users/gupta/OneDrive/Desktop/Mailmind/venv/Scripts/python.exe main.py`
3. **Open Terminal 2 (PowerShell) from project root**
4. **Start frontend**
  - `Set-Location .\frontend`
  - `npm start`
3. Open UI at `http://localhost:3000`
4. Confirm backend health (`/health`) is OK.

### Optional build check
- In `frontend/`: `npm run build`

---

## 3) Gmail login behavior (important)

### Do I need to login every time an email is received?
**No.** Usually only the first time (or when token is expired/revoked).

MailMind stores OAuth token at:
- `backend/token.json`

As long as this token remains valid, MailMind auto-refreshes and does not ask every time.

MailMind now also caches OAuth credentials/services in backend runtime, so repeated API calls in one session should not trigger repeated auth prompts.

### You may be asked to login again if:
- `token.json` is deleted
- Google access is revoked
- OAuth scopes/credentials changed
- refresh token becomes invalid

### LLM provider fallback behavior
- App now supports **Gemini + Groq fallback** in `backend/reply_generator.py`.
- With `LLM_PROVIDER=auto`:
  1. tries Gemini first
  2. if Gemini fails (quota/key issue), tries Groq automatically

---

## 4) Daily test/use flow

1. Send a test email from another account to connected Gmail account.
2. Keep that email unread in Gmail.
3. In UI, go to `Emails` page.
4. Click **Sync Inbox Now**.
5. Check processed result in table and Dashboard stream.

> Important: Dashboard does **not** auto-process unread emails every 30 seconds anymore.
> Processing happens only when you click a Sync button (Dashboard / Emails / Calendar).

Because app marks successfully processed messages as read, they are not repeatedly reprocessed.

### Meeting booking check (simple English)

For emails that look like meeting requests, MailMind now:

1. Reads proposed date/time from the email text (example: `tomorrow 10 AM`).
2. Checks your **Google Calendar free/busy** for that slot.
3. If slot is free, reply can confirm that slot.
4. If slot is busy, auto-reply asks sender to share alternate slots (no booking is created).
5. If date/time is unclear, reply asks sender to confirm exact date/time.

When action is `auto_send` and slot is free, MailMind can also create a calendar event on your primary calendar.

Extra safety added:
- Duplicate guard by email ID (already-processed/replied message is skipped)
- Backend processing lock (prevents concurrent double-processing)

---

## 5) Pages and what they do

- `Dashboard`
  - Polls backend for analytics/history and shows recent processed stream.
  - Has **Sync Inbox Now** button for explicit processing trigger.
  - **View Full History** opens full history on Emails page.

- `Emails`
  - Shows persisted processing history from backend `/history`.
  - Includes `Sync Inbox Now` for manual processing trigger.

- `Settings`
  - API/model status UI
  - Supports:
    - clear vector memory (`/clear-memory`)
    - reset runtime analytics (`/reset-analytics`)

---

## 6) Key backend endpoints

- `GET /health` → API health
- `POST /process-emails` → process unread inbox emails now
- `GET /history` → full persisted history (latest first)
- `POST /history/clear` → clear history records
- `GET /analytics` → runtime counters
- `POST /reset-analytics` → reset counters
- `POST /clear-memory` → clear Chroma memory store

---

## 6.1) Environment variables (current setup)

In `.env` and `backend/.env`:

- `GEMINI_API_KEY=...`
- `GROQ_API_KEY=...`
- `GROQ_MODEL=llama-3.1-8b-instant`
- `LLM_PROVIDER=auto`

You can force one provider:
- `LLM_PROVIDER=gemini`
- `LLM_PROVIDER=groq`

---

## 7) Troubleshooting

### Frontend shows no emails
- Ensure unread emails exist in connected Gmail inbox.
- Click **Sync Inbox Now**.
- Check backend terminal for errors.

### Gemini quota exceeded
- Keep `LLM_PROVIDER=auto` so app falls back to Groq.
- If both providers fail, verify keys and billing/quota.

### Wrong Gmail account
- Delete `backend/token.json` and re-auth with correct account.

### OAuth callback fails
- Use manual URL paste fallback shown in terminal.

### Dashboard numbers reset after restart
- Analytics counters are runtime counters.
- Full processed records remain in `/history`.

---

## 8) Suggested clean test routine

1. Start backend
2. Start frontend
3. Send one test mail
4. Sync from UI
5. Validate row details (spam/sentiment/intent/action/reply)
6. Repeat with scenarios in `EMAIL_TEST_SCENARIOS.md`

### Quick restart commands (exact)

Backend (from root):
- `Set-Location .\backend`
- `c:/Users/gupta/OneDrive/Desktop/Mailmind/venv/Scripts/python.exe main.py`

Frontend (from root):
- `Set-Location .\frontend`
- `npm start`

---

## 9) Safety note

When intent confidence is high (`>=85`), action may be `auto_send`.
Use test accounts while validating to avoid unintended replies to real customers.
