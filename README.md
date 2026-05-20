# Sample AI Tutor App (Flask + OpenRouter + SQLite)

A Flask app that sends tutor questions to OpenRouter and stores all responses in SQLite so everyone can see recent saved sessions.

- **Model**: `google/gemini-2.5-flash-lite`
- **Endpoint**: `POST /api/v1/chat/completions`
- **Structured JSON response** using `response_format.type = json_schema`
- **Persistence**: SQLite database (`tutor_sessions.db` by default)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export OPENROUTER_API_KEY="..."
python app.py
```

Open: http://127.0.0.1:5000

## Environment variables

- `OPENROUTER_API_KEY` (required)
- `DATABASE_PATH` (optional, default: `tutor_sessions.db`)

## API routes

### `POST /api/tutor`
Creates a tutor response via OpenRouter, validates/parses JSON output, and saves session to SQLite.

Request body:

```json
{
  "grade_level": "middle school",
  "question": "Why do we invert and multiply when dividing fractions?"
}
```

### `GET /api/history`
Returns up to 50 most recent saved tutor sessions.

