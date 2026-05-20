import json
import os
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"


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
        return jsonify({"model": MODEL, "result": parsed})
    except requests.HTTPError:
        return jsonify({"error": "OpenRouter request failed", "details": resp.text}), resp.status_code
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": "Invalid AI response format", "details": str(exc)}), 502
    except requests.RequestException as exc:
        return jsonify({"error": "Network error while calling OpenRouter", "details": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True)
