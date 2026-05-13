# MailMind

MailMind is an AI-powered email assistant that connects to Gmail, understands incoming messages, and generates professional replies. It also checks Google Calendar for meeting requests and keeps a memory of past conversations for better responses. A React dashboard shows live analytics, processed history, and automation status.

---

## ✨ Simple Overview (For Anyone)

MailMind helps you manage a busy inbox by doing three big jobs:

1. **Understand** emails (spam, intent, sentiment)
2. **Decide** whether to auto-reply, flag for review, or escalate
3. **Respond** with safe, context-aware replies (and avoid calendar conflicts)

What you get:

- **Inbox triage** so urgent or spam messages are handled correctly
- **Automatic replies** that stay professional and safe
- **Meeting intelligence** with free/busy checks before confirming time slots
- **A clean dashboard** to monitor everything in real time

---

## 🧠 Technical Details (Complete)

### AI/ML Pipeline
- **Spam Detection**: Sentence Transformers embeddings + **XGBoost** classifier
- **Intent Classification**: Sentence Transformers embeddings + **SVM (RBF)**
- **Sentiment Analysis**: **VADER** (offline rule-based)
- **Reply Generation**: **Gemini** with **Groq** fallback (LLM_PROVIDER=auto)
- **Memory**: **ChromaDB** persistent vector store with offline embeddings

### Backend (FastAPI)
- Gmail + Calendar integration via Google APIs
- Processing lock + duplicate guard to prevent re-processing
- Key endpoints:
  - `POST /process-emails` → process unread inbox now
  - `GET /history` → processed email history
  - `GET /analytics` → live counters
  - `GET /calendar/meetings` → meeting requests + upcoming events
  - `POST /clear-memory` → reset vector memory
  - `POST /reset-analytics` → reset counters
  - `GET /health` → API health check

### Frontend (React)
- **Dashboard**: live stats, charts, and pipeline indicators
- **Emails**: searchable history with intent, sentiment, and reply preview
- **Calendar**: meeting request status and live Google Calendar events
- **Settings**: model health, memory reset, and API status

---

## 📁 Project Structure

```
Mailmind/
  backend/            # FastAPI backend + Gmail/Calendar + ML pipeline
  frontend/           # React dashboard
  models/             # ML assets, datasets, vector DB
  APP_USAGE_GUIDE.md  # Usage instructions
  EMAIL_TEST_SCENARIOS.md
```

---

## ✅ Local Setup (Step-by-Step)

### 1) Prerequisites
- Python 3.12+
- Node.js + npm
- Google API credentials JSON file

### 2) Install Backend Dependencies

From project root:

```
cd backend
pip install fastapi uvicorn google-auth google-auth-oauthlib google-api-python-client \
  sentence-transformers scikit-learn xgboost pandas chromadb vaderSentiment \
  python-dotenv numpy google-generativeai
```

### 3) Environment Variables
Create `.env` at project root **and** `backend/.env` with:

```
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
LLM_PROVIDER=auto
```

Optional:
```
APP_TIMEZONE=Asia/Kolkata
MEETING_DURATION_MINUTES=30
```

### 4) Google API Setup
- Enable **Gmail API** and **Google Calendar API** in Google Cloud Console
- Download OAuth credentials JSON and place it at:
  `backend/credentials.json`

### 5) Start Backend

```
cd backend
python main.py
```

Backend runs at `http://localhost:8000`.

### 6) Start Frontend

```
cd frontend
npm install
npm start
```

Frontend runs at `http://localhost:3000`.

---

## ✅ Operational Notes

- Gmail OAuth tokens are stored in `backend/token.json`
- If Google auth fails, delete `token.json` and re-auth
- `models/email_history.json` persists processed emails
- Use test accounts while validating auto-reply features
