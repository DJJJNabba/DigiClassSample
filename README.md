# Sample AI Tutor App (Flask + OpenRouter)

A minimal Flask web app that sends tutor questions to OpenRouter using:
- **Model**: `google/gemini-2.5-flash-lite`
- **Endpoint**: `POST /api/v1/chat/completions`
- **Structured JSON response** using `response_format.type = json_schema`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export OPENROUTER_API_KEY="..."
python app.py
```

Open http://127.0.0.1:5000

## API route

`POST /api/tutor`

Request body:

```json
{
  "grade_level": "middle school",
  "question": "Why do we invert and multiply when dividing fractions?"
}
```

Response shape:

```json
{
  "model": "google/gemini-2.5-flash-lite",
  "result": {
    "concept_summary": "...",
    "explanation": "...",
    "worked_example": "...",
    "check_understanding": ["...", "..."],
    "next_step_hint": "..."
  }
}
```
