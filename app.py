"""DigiClass — an AI-assisted learning platform.

A Flask application with session-based authentication, role-based access
control, and an SQLite datastore. Teachers and students generate practice
quizzes and flashcard sets with AI assistance; teachers review and publish
content to a shared library that students practise against.
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

import requests
from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import seed

app = Flask(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────
# SECRET_KEY signs the session cookie. Always set a stable value in production
# (export SECRET_KEY=...). A random key is generated as a fallback so the app
# still boots in development, but sessions will not survive a restart.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Enable secure cookies when served over HTTPS (recommended behind a TLS proxy).
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
DB_PATH = os.getenv("DATABASE_PATH", "digiclass.db")

ROLES = ("student", "teacher", "admin")


# ─── Database bootstrap ─────────────────────────────────────────────────────────


def _bootstrap_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_by INTEGER NOT NULL REFERENCES users(id),
            subject_id INTEGER REFERENCES subjects(id),
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium'
                CHECK(difficulty IN ('easy','medium','hard')),
            content_type TEXT NOT NULL CHECK(content_type IN ('quiz','flashcard')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','approved','rejected')),
            reviewed_by INTEGER REFERENCES users(id),
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            question_order INTEGER NOT NULL DEFAULT 0,
            question TEXT NOT NULL,
            options_json TEXT NOT NULL,
            explanation TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            card_order INTEGER NOT NULL DEFAULT 0,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            card_type TEXT NOT NULL DEFAULT 'summary',
            tags_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS user_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            question_id INTEGER NOT NULL REFERENCES quiz_questions(id),
            selected_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            answered_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_content_status ON content_items(status);
        CREATE INDEX IF NOT EXISTS idx_content_subject ON content_items(subject_id);
        CREATE INDEX IF NOT EXISTS idx_questions_content ON quiz_questions(content_id);
        CREATE INDEX IF NOT EXISTS idx_responses_user ON user_responses(user_id);
        """
    )
    conn.commit()
    conn.close()

    # Populate a fresh database with a realistic demonstration dataset.
    seed.seed_if_empty(DB_PATH)


_bootstrap_db()


# ─── DB helpers ─────────────────────────────────────────────────────────────────


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_user(user_id: int) -> dict | None:
    row = get_db().execute(
        "SELECT id, name, email, role, active, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def current_user() -> dict | None:
    """Return the authenticated user for this request, or None."""
    uid = session.get("user_id")
    if not uid:
        return None
    user = get_user(uid)
    if not user or not user["active"]:
        session.clear()
        return None
    return user


# ─── Auth guards ────────────────────────────────────────────────────────────────


def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if current_user() is None:
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = current_user()
            if user is None:
                return jsonify({"error": "Authentication required"}), 401
            if user["role"] not in roles:
                return jsonify({"error": "You do not have permission to do that"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ─── Page routes ────────────────────────────────────────────────────────────────


@app.route("/")
def home() -> Any:
    user = current_user()
    if user is None:
        return redirect(url_for("login_page"))
    return render_template("index.html", user=user)


@app.route("/login")
def login_page() -> Any:
    if current_user() is not None:
        return redirect(url_for("home"))
    return render_template("auth.html", mode="login")


@app.route("/register")
def register_page() -> Any:
    if current_user() is not None:
        return redirect(url_for("home"))
    return render_template("auth.html", mode="register")


@app.route("/logout")
def logout() -> Any:
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/health")
def health() -> Any:
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


# ─── Auth API ───────────────────────────────────────────────────────────────────


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


@app.route("/api/auth/register", methods=["POST"])
def api_register() -> Any:
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = _normalise_email(data.get("email"))
    password = data.get("password") or ""

    if not name or len(name) < 2:
        return jsonify({"error": "Please enter your full name"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Please enter a valid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur = db.execute(
            """INSERT INTO users (name, email, password_hash, role, active, created_at)
               VALUES (?, ?, ?, 'student', 1, ?)""",
            (name, email, generate_password_hash(password), now),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with that email already exists"}), 409

    session.clear()
    session["user_id"] = cur.lastrowid
    return jsonify(get_user(cur.lastrowid)), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login() -> Any:
    data = request.get_json(silent=True) or {}
    email = _normalise_email(data.get("email"))
    password = data.get("password") or ""

    row = get_db().execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect email or password"}), 401
    if not row["active"]:
        return jsonify({"error": "This account has been deactivated"}), 403

    session.clear()
    session["user_id"] = row["id"]
    return jsonify(get_user(row["id"]))


@app.route("/api/auth/logout", methods=["POST"])
def api_logout() -> Any:
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def api_me() -> Any:
    user = current_user()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user)


# ─── Subjects ───────────────────────────────────────────────────────────────────


@app.route("/api/subjects", methods=["GET"])
@login_required
def list_subjects() -> Any:
    rows = get_db().execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/subjects", methods=["POST"])
@role_required("admin")
def create_subject() -> Any:
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Subject name is required"}), 400

    db = get_db()
    try:
        db.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        db.commit()
        row = db.execute("SELECT * FROM subjects WHERE name = ?", (name,)).fetchone()
        return jsonify(dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Subject already exists"}), 409


@app.route("/api/subjects/<int:sid>", methods=["PATCH"])
@role_required("admin")
def update_subject(sid: int) -> Any:
    data = request.get_json(silent=True) or {}
    db = get_db()
    if "active" in data:
        db.execute(
            "UPDATE subjects SET active = ? WHERE id = ?",
            (1 if data["active"] else 0, sid),
        )
        db.commit()
    row = db.execute("SELECT * FROM subjects WHERE id = ?", (sid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)


# ─── Users (admin) ──────────────────────────────────────────────────────────────


@app.route("/api/users", methods=["GET"])
@role_required("admin")
def list_users() -> Any:
    rows = get_db().execute(
        """SELECT u.id, u.name, u.email, u.role, u.active, u.created_at,
                  (SELECT COUNT(*) FROM content_items ci WHERE ci.created_by = u.id) AS content_count,
                  (SELECT COUNT(*) FROM user_responses ur WHERE ur.user_id = u.id) AS response_count
           FROM users u ORDER BY u.role, u.name"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/users/<int:uid>/role", methods=["PATCH"])
@role_required("admin")
def update_user_role(uid: int) -> Any:
    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "")
    if new_role not in ROLES:
        return jsonify({"error": "Invalid role. Must be student, teacher, or admin"}), 400

    me = current_user()
    if uid == me["id"] and new_role != "admin":
        return jsonify({"error": "You cannot remove your own admin access"}), 400

    db = get_db()
    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, uid))
    db.commit()
    row = db.execute("SELECT id, name, role FROM users WHERE id = ?", (uid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)


# ─── AI content generation ──────────────────────────────────────────────────────


@app.route("/api/generate", methods=["POST"])
@login_required
def generate_content() -> Any:
    if not OPENROUTER_API_KEY:
        return jsonify({
            "error": "AI generation is not configured on this server.",
            "details": "Set the OPENROUTER_API_KEY environment variable to enable it.",
        }), 503

    user = current_user()
    data = request.get_json(silent=True) or {}

    subject_id = data.get("subject_id")
    topic = (data.get("topic") or "").strip()
    difficulty = data.get("difficulty", "medium")
    content_type = data.get("content_type", "quiz")
    num_items = min(max(int(data.get("num_items", 5)), 2), 10)

    if not topic:
        return jsonify({"error": "Topic is required"}), 400
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    if content_type not in ("quiz", "flashcard"):
        content_type = "quiz"

    subject_name = ""
    if subject_id:
        sub = get_db().execute(
            "SELECT name FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        subject_name = sub["name"] if sub else ""

    if content_type == "quiz":
        schema = {
            "name": "quiz_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "subject": {"type": "string"},
                    "difficulty": {"type": "string"},
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "answers": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "text": {"type": "string"},
                                            "correct": {"type": "boolean"},
                                        },
                                        "required": ["id", "text", "correct"],
                                        "additionalProperties": False,
                                    },
                                },
                                "explanation": {"type": "string"},
                            },
                            "required": ["question", "answers", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["topic", "subject", "difficulty", "questions"],
                "additionalProperties": False,
            },
        }
        prompt = (
            f"Generate exactly {num_items} multiple-choice quiz questions about '{topic}'"
            f"{' for the subject ' + subject_name if subject_name else ''}. "
            f"Difficulty level: {difficulty}. "
            "Each question must have exactly 4 answer options (id: a, b, c, d) with exactly one correct. "
            "Include a clear explanation for the correct answer. "
            "Target senior secondary students (Year 11-12 level)."
        )
    else:
        schema = {
            "name": "flashcard_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "category": {"type": "string"},
                    "difficulty": {"type": "string"},
                    "flashcards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "type": {"type": "string"},
                                "front": {"type": "string"},
                                "back": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["id", "type", "front", "back", "tags"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["topic", "category", "difficulty", "flashcards"],
                "additionalProperties": False,
            },
        }
        prompt = (
            f"Generate exactly {num_items} flashcards about '{topic}'"
            f"{' for the subject ' + subject_name if subject_name else ''}. "
            f"Difficulty: {difficulty}. "
            "Mix 'summary' type (key concept overview) and 'detail' type (specific facts/examples). "
            "Include relevant tags for each card. Target Year 11-12 students."
        )

    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert educational content creator for senior secondary students (Year 11-12). "
                    "Generate high-quality, curriculum-aligned learning content as valid JSON matching the requested schema. "
                    "Ensure content is accurate, educationally appropriate, and appropriately challenging."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_schema", "json_schema": schema},
        "temperature": 0.7,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        ai_data = resp.json()
        content_str = ai_data["choices"][0]["message"]["content"]
        parsed = json.loads(content_str)

        now = datetime.now(timezone.utc).isoformat()
        db = get_db()
        cur = db.execute(
            """INSERT INTO content_items
               (created_by, subject_id, topic, difficulty, content_type, status, created_at, raw_json)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (user["id"], subject_id, topic, difficulty, content_type, now, json.dumps(parsed)),
        )
        content_id = cur.lastrowid

        if content_type == "quiz":
            for i, q in enumerate(parsed.get("questions", [])):
                db.execute(
                    """INSERT INTO quiz_questions
                       (content_id, question_order, question, options_json, explanation)
                       VALUES (?, ?, ?, ?, ?)""",
                    (content_id, i, q["question"], json.dumps(q["answers"]), q["explanation"]),
                )
        else:
            for i, fc in enumerate(parsed.get("flashcards", [])):
                db.execute(
                    """INSERT INTO flashcards
                       (content_id, card_order, front, back, card_type, tags_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        content_id,
                        i,
                        fc["front"],
                        fc["back"],
                        fc.get("type", "summary"),
                        json.dumps(fc.get("tags", [])),
                    ),
                )

        db.commit()
        item_count = len(parsed.get("questions" if content_type == "quiz" else "flashcards", []))
        return jsonify(
            {
                "content_id": content_id,
                "content_type": content_type,
                "topic": topic,
                "status": "pending",
                "item_count": item_count,
                "preview": parsed,
                "message": f"Generated {item_count} {'questions' if content_type == 'quiz' else 'flashcards'} and saved as pending. Awaiting teacher approval.",
            }
        ), 201

    except requests.HTTPError:
        return jsonify({"error": "AI provider request failed", "details": resp.text}), 502
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": "Invalid AI response format", "details": str(exc)}), 502
    except requests.RequestException as exc:
        return jsonify({"error": "Network error contacting the AI provider", "details": str(exc)}), 502


# ─── Content library ────────────────────────────────────────────────────────────


@app.route("/api/content", methods=["GET"])
@login_required
def list_content() -> Any:
    user = current_user()

    filters: list[str] = []
    params: list[Any] = []

    if user["role"] == "student":
        filters.append("(ci.status = 'approved' OR ci.created_by = ?)")
        params.append(user["id"])

    status = request.args.get("status")
    if status and status in ("pending", "approved", "rejected"):
        filters.append("ci.status = ?")
        params.append(status)

    subject_id = request.args.get("subject_id")
    if subject_id:
        filters.append("ci.subject_id = ?")
        params.append(int(subject_id))

    content_type = request.args.get("type")
    if content_type in ("quiz", "flashcard"):
        filters.append("ci.content_type = ?")
        params.append(content_type)

    difficulty = request.args.get("difficulty")
    if difficulty in ("easy", "medium", "hard"):
        filters.append("ci.difficulty = ?")
        params.append(difficulty)

    search = (request.args.get("q") or "").strip()
    if search:
        filters.append("ci.topic LIKE ?")
        params.append(f"%{search}%")

    where = "WHERE " + " AND ".join(filters) if filters else ""

    rows = get_db().execute(
        f"""SELECT ci.id, ci.topic, ci.difficulty, ci.content_type, ci.status,
                   ci.created_at, ci.reviewed_at, ci.subject_id,
                   u.name AS creator_name, ci.created_by,
                   s.name AS subject_name,
                   ru.name AS reviewer_name,
                   (SELECT COUNT(*) FROM quiz_questions q WHERE q.content_id = ci.id) AS question_count,
                   (SELECT COUNT(*) FROM flashcards f WHERE f.content_id = ci.id) AS card_count
            FROM content_items ci
            JOIN users u ON ci.created_by = u.id
            LEFT JOIN subjects s ON ci.subject_id = s.id
            LEFT JOIN users ru ON ci.reviewed_by = ru.id
            {where}
            ORDER BY ci.created_at DESC, ci.id DESC LIMIT 200""",
        params,
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["item_count"] = (
            item.pop("question_count") if item["content_type"] == "quiz" else item.pop("card_count")
        )
        item.pop("question_count", None)
        item.pop("card_count", None)
        result.append(item)

    return jsonify(result)


@app.route("/api/content/<int:cid>", methods=["GET"])
@login_required
def get_content(cid: int) -> Any:
    user = current_user()
    db = get_db()
    row = db.execute(
        """SELECT ci.*, u.name AS creator_name, s.name AS subject_name
           FROM content_items ci
           JOIN users u ON ci.created_by = u.id
           LEFT JOIN subjects s ON ci.subject_id = s.id
           WHERE ci.id = ?""",
        (cid,),
    ).fetchone()

    if not row:
        return jsonify({"error": "Content not found"}), 404

    item = dict(row)

    if (
        user["role"] == "student"
        and item["status"] != "approved"
        and item["created_by"] != user["id"]
    ):
        return jsonify({"error": "Access denied — content is not yet approved"}), 403

    if item["content_type"] == "quiz":
        qs = db.execute(
            "SELECT * FROM quiz_questions WHERE content_id = ? ORDER BY question_order",
            (cid,),
        ).fetchall()
        item["questions"] = []
        for q in qs:
            qd = dict(q)
            qd["options"] = json.loads(qd.pop("options_json"))
            resp = db.execute(
                """SELECT * FROM user_responses WHERE user_id = ? AND question_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (user["id"], qd["id"]),
            ).fetchone()
            qd["my_response"] = dict(resp) if resp else None
            item["questions"].append(qd)
    else:
        fcs = db.execute(
            "SELECT * FROM flashcards WHERE content_id = ? ORDER BY card_order",
            (cid,),
        ).fetchall()
        item["flashcards"] = []
        for fc in fcs:
            fcd = dict(fc)
            fcd["tags"] = json.loads(fcd.pop("tags_json"))
            item["flashcards"].append(fcd)

    item.pop("raw_json", None)
    return jsonify(item)


@app.route("/api/content/<int:cid>/status", methods=["PATCH"])
@role_required("teacher", "admin")
def update_content_status(cid: int) -> Any:
    user = current_user()
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "Invalid status. Must be approved, rejected, or pending"}), 400

    db = get_db()
    db.execute(
        "UPDATE content_items SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
        (new_status, user["id"], datetime.now(timezone.utc).isoformat(), cid),
    )
    db.commit()
    row = db.execute(
        """SELECT ci.id, ci.topic, ci.status, ci.difficulty, ci.content_type,
                  ci.reviewed_at, u.name AS reviewer_name
           FROM content_items ci LEFT JOIN users u ON ci.reviewed_by = u.id
           WHERE ci.id = ?""",
        (cid,),
    ).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)


# ─── Practice ───────────────────────────────────────────────────────────────────


@app.route("/api/answer", methods=["POST"])
@login_required
def submit_answer() -> Any:
    user = current_user()
    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    selected_option = (data.get("selected_option") or "").strip()

    if not question_id or not selected_option:
        return jsonify({"error": "question_id and selected_option are required"}), 400

    db = get_db()
    q = db.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,)).fetchone()
    if not q:
        return jsonify({"error": "Question not found"}), 404

    options = json.loads(q["options_json"])
    correct = next((o for o in options if o["correct"]), None)
    is_correct = bool(correct and selected_option == correct["id"])

    db.execute(
        """INSERT INTO user_responses
           (user_id, question_id, selected_option, is_correct, answered_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            user["id"],
            question_id,
            selected_option,
            1 if is_correct else 0,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()

    return jsonify(
        {
            "is_correct": is_correct,
            "correct_option": correct["id"] if correct else None,
            "correct_text": correct["text"] if correct else None,
            "explanation": q["explanation"],
        }
    )


@app.route("/api/progress", methods=["GET"])
@login_required
def get_progress() -> Any:
    user = current_user()
    user_id = user["id"]
    db = get_db()

    total = db.execute(
        "SELECT COUNT(*) FROM user_responses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    correct = db.execute(
        "SELECT COUNT(*) FROM user_responses WHERE user_id = ? AND is_correct = 1", (user_id,)
    ).fetchone()[0]
    unique_qs = db.execute(
        "SELECT COUNT(DISTINCT question_id) FROM user_responses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    generated = db.execute(
        "SELECT COUNT(*) FROM content_items WHERE created_by = ?", (user_id,)
    ).fetchone()[0]

    subject_rows = db.execute(
        """SELECT COALESCE(s.name, 'Unclassified') AS subject,
                  COUNT(ur.id) AS attempts,
                  SUM(ur.is_correct) AS correct_count
           FROM user_responses ur
           JOIN quiz_questions qq ON ur.question_id = qq.id
           JOIN content_items ci ON qq.content_id = ci.id
           LEFT JOIN subjects s ON ci.subject_id = s.id
           WHERE ur.user_id = ?
           GROUP BY ci.subject_id
           ORDER BY attempts DESC""",
        (user_id,),
    ).fetchall()

    recent_rows = db.execute(
        """SELECT ur.answered_at, ur.is_correct, ur.selected_option,
                  qq.question, ci.topic
           FROM user_responses ur
           JOIN quiz_questions qq ON ur.question_id = qq.id
           JOIN content_items ci ON qq.content_id = ci.id
           WHERE ur.user_id = ?
           ORDER BY ur.id DESC LIMIT 10""",
        (user_id,),
    ).fetchall()

    return jsonify(
        {
            "total_attempts": total,
            "correct_answers": correct,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "unique_questions": unique_qs,
            "content_generated": generated,
            "subject_progress": [dict(r) for r in subject_rows],
            "recent_activity": [dict(r) for r in recent_rows],
        }
    )


@app.route("/api/stats", methods=["GET"])
@role_required("teacher", "admin")
def get_stats() -> Any:
    db = get_db()
    by_status = db.execute(
        "SELECT status, COUNT(*) AS count FROM content_items GROUP BY status"
    ).fetchall()
    by_type = db.execute(
        "SELECT content_type, COUNT(*) AS count FROM content_items GROUP BY content_type"
    ).fetchall()
    by_subject = db.execute(
        """SELECT COALESCE(s.name, 'Unclassified') AS subject, COUNT(*) AS count
           FROM content_items ci LEFT JOIN subjects s ON ci.subject_id = s.id
           GROUP BY ci.subject_id ORDER BY count DESC""",
    ).fetchall()
    top_students = db.execute(
        """SELECT u.name, COUNT(ur.id) AS attempts, SUM(ur.is_correct) AS correct
           FROM user_responses ur JOIN users u ON ur.user_id = u.id
           GROUP BY ur.user_id ORDER BY attempts DESC LIMIT 6""",
    ).fetchall()

    return jsonify(
        {
            "total_users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "total_students": db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'student'"
            ).fetchone()[0],
            "total_content": db.execute("SELECT COUNT(*) FROM content_items").fetchone()[0],
            "total_responses": db.execute("SELECT COUNT(*) FROM user_responses").fetchone()[0],
            "content_by_status": [dict(r) for r in by_status],
            "content_by_type": [dict(r) for r in by_type],
            "content_by_subject": [dict(r) for r in by_subject],
            "top_students": [dict(r) for r in top_students],
        }
    )


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1", port=int(os.getenv("PORT", "5000")))
