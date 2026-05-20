import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"
DB_PATH = os.getenv("DATABASE_PATH", "tutor_sessions.db")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def init_db() -> None:
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tutor_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            question TEXT NOT NULL,
            concept_summary TEXT NOT NULL,
            explanation TEXT NOT NULL,
            worked_example TEXT NOT NULL,
            check_understanding_json TEXT NOT NULL,
            next_step_hint TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
        """
    )
    db.commit()


@app.before_request
def before_request() -> None:
    init_db()


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def home() -> str:
    return render_template("index.html", model=MODEL)


@app.route("/api/tutor", methods=["POST"])
def tutor() -> Any:
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "OPENROUTER_API_KEY is not configured."}), 500

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    grade_level = (payload.get("grade_level") or "middle school").strip()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    schema = {
        "name": "ai_tutor_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "concept_summary": {"type": "string"},
                "explanation": {"type": "string"},
                "worked_example": {"type": "string"},
                "check_understanding": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 4,
                },
                "next_step_hint": {"type": "string"},
            },
            "required": [
                "concept_summary",
                "explanation",
                "worked_example",
                "check_understanding",
                "next_step_hint",
            ],
            "additionalProperties": False,
        },
    }

    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an encouraging AI tutor. Adapt explanations to the student's level, "
                    "ask short check-for-understanding questions, and keep responses concise."
                ),
            },
            {
                "role": "user",
                "content": f"Grade level: {grade_level}. Student question: {question}",
            },
        ],
        "response_format": {"type": "json_schema", "json_schema": schema},
        "temperature": 0.4,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        created_at = datetime.now(timezone.utc).isoformat()
        db = get_db()
        db.execute(
            """
            INSERT INTO tutor_sessions (
                created_at, grade_level, question, concept_summary, explanation,
                worked_example, check_understanding_json, next_step_hint, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                grade_level,
                question,
                parsed["concept_summary"],
                parsed["explanation"],
                parsed["worked_example"],
                json.dumps(parsed["check_understanding"]),
                parsed["next_step_hint"],
                json.dumps(parsed),
            ),
        )
        db.commit()

        return jsonify({"model": MODEL, "result": parsed})
    except requests.HTTPError:
        return jsonify({"error": "OpenRouter request failed", "details": resp.text}), resp.status_code
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": "Invalid AI response format", "details": str(exc)}), 502
    except requests.RequestException as exc:
        return jsonify({"error": "Network error while calling OpenRouter", "details": str(exc)}), 502


@app.route("/api/history", methods=["GET"])
def history() -> Any:
    rows = get_db().execute(
        """
        SELECT id, created_at, grade_level, question, concept_summary, explanation,
               worked_example, check_understanding_json, next_step_hint, raw_json
        FROM tutor_sessions
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    sessions = []
    for row in rows:
        sessions.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "grade_level": row["grade_level"],
                "question": row["question"],
                "result": {
                    "concept_summary": row["concept_summary"],
                    "explanation": row["explanation"],
                    "worked_example": row["worked_example"],
                    "check_understanding": json.loads(row["check_understanding_json"]),
                    "next_step_hint": row["next_step_hint"],
                },
                "raw_json": json.loads(row["raw_json"]),
            }
        )

    return jsonify({"count": len(sessions), "sessions": sessions})


if __name__ == "__main__":
    app.run(debug=True)
