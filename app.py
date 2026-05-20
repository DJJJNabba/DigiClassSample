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
DB_PATH = os.getenv("DATABASE_PATH", "tutor.db")

DEMO_USERS = [
    (1, "Hamish", "student"),
    (2, "Alex", "teacher"),
    (3, "Ruth", "admin"),
]

DEMO_SUBJECTS = [
    (1, "Digital Solutions"),
    (2, "Mathematics"),
    (3, "Biology"),
    (4, "Chemistry"),
    (5, "English"),
    (6, "History"),
]

SAMPLE_QUIZ_1 = {
    "topic": "SQL Fundamentals",
    "subject": "Digital Solutions",
    "difficulty": "medium",
    "questions": [
        {
            "question": "Which SQL clause is used to filter records after a GROUP BY has been applied?",
            "answers": [
                {"id": "a", "text": "WHERE", "correct": False},
                {"id": "b", "text": "HAVING", "correct": True},
                {"id": "c", "text": "FILTER", "correct": False},
                {"id": "d", "text": "LIMIT", "correct": False},
            ],
            "explanation": "HAVING is used to filter grouped results, whereas WHERE filters rows before grouping.",
        },
        {
            "question": "What does SQL stand for?",
            "answers": [
                {"id": "a", "text": "Structured Query Language", "correct": True},
                {"id": "b", "text": "Simple Query Language", "correct": False},
                {"id": "c", "text": "Sequential Query Logic", "correct": False},
                {"id": "d", "text": "Standard Query Library", "correct": False},
            ],
            "explanation": "SQL stands for Structured Query Language, the standard language for relational database management.",
        },
        {
            "question": "Which SQL command retrieves data from a table?",
            "answers": [
                {"id": "a", "text": "INSERT", "correct": False},
                {"id": "b", "text": "UPDATE", "correct": False},
                {"id": "c", "text": "SELECT", "correct": True},
                {"id": "d", "text": "FETCH", "correct": False},
            ],
            "explanation": "SELECT is used to query and retrieve data from one or more database tables.",
        },
        {
            "question": "What is a PRIMARY KEY in a relational database?",
            "answers": [
                {"id": "a", "text": "A key used to encrypt data", "correct": False},
                {"id": "b", "text": "A unique identifier for each row in a table", "correct": True},
                {"id": "c", "text": "The first column in any table", "correct": False},
                {"id": "d", "text": "A foreign reference to another table", "correct": False},
            ],
            "explanation": "A PRIMARY KEY uniquely identifies each record in a table and cannot contain NULL values.",
        },
    ],
}

SAMPLE_QUIZ_2 = {
    "topic": "Cybersecurity Principles",
    "subject": "Digital Solutions",
    "difficulty": "hard",
    "questions": [
        {
            "question": "Which attack involves an attacker intercepting communication between two parties?",
            "answers": [
                {"id": "a", "text": "SQL Injection", "correct": False},
                {"id": "b", "text": "Man-in-the-Middle (MitM)", "correct": True},
                {"id": "c", "text": "Denial of Service", "correct": False},
                {"id": "d", "text": "Phishing", "correct": False},
            ],
            "explanation": "A Man-in-the-Middle attack occurs when an attacker secretly relays and possibly alters communications between two parties.",
        },
        {
            "question": "What does HTTPS use to secure data transmission?",
            "answers": [
                {"id": "a", "text": "Base64 encoding", "correct": False},
                {"id": "b", "text": "TLS/SSL encryption", "correct": True},
                {"id": "c", "text": "MD5 hashing", "correct": False},
                {"id": "d", "text": "ZIP compression", "correct": False},
            ],
            "explanation": "HTTPS uses TLS (Transport Layer Security) or its predecessor SSL to encrypt data transmitted between client and server.",
        },
        {
            "question": "What is the principle of least privilege?",
            "answers": [
                {"id": "a", "text": "Users should have maximum access for efficiency", "correct": False},
                {"id": "b", "text": "Only admins should access the system", "correct": False},
                {"id": "c", "text": "Users should only have the minimum access needed for their role", "correct": True},
                {"id": "d", "text": "Passwords should be as simple as possible", "correct": False},
            ],
            "explanation": "The principle of least privilege limits user access rights to only what is necessary for their role, reducing security risks.",
        },
    ],
}

SAMPLE_FLASHCARDS = {
    "topic": "Caesar Cipher",
    "category": "Cryptography",
    "difficulty": "easy",
    "flashcards": [
        {
            "id": 1,
            "type": "summary",
            "front": "What is the Caesar Cipher?",
            "back": "A substitution cipher where each letter in the plaintext is shifted a fixed number of positions down the alphabet.",
            "tags": ["definition", "overview"],
        },
        {
            "id": 2,
            "type": "summary",
            "front": "Who invented the Caesar Cipher and when?",
            "back": "Julius Caesar, used around 58 BC to protect military communications.",
            "tags": ["history", "origin"],
        },
        {
            "id": 3,
            "type": "detail",
            "front": "How does a Caesar Cipher with a shift of 3 encode the letter 'A'?",
            "back": "A → D. Each letter moves 3 places forward: A→D, B→E, C→F, and so on.",
            "tags": ["mechanics", "example"],
        },
        {
            "id": 4,
            "type": "detail",
            "front": "How is a Caesar Cipher decoded?",
            "back": "Reverse the shift — subtract the key number from each letter's position in the alphabet.",
            "tags": ["decryption", "mechanics"],
        },
        {
            "id": 5,
            "type": "detail",
            "front": "Why is the Caesar Cipher considered insecure today?",
            "back": "There are only 25 possible shifts, making it trivially easy to brute-force. Frequency analysis can also crack it.",
            "tags": ["security", "weakness"],
        },
    ],
}

SAMPLE_PENDING_QUIZ = {
    "topic": "Recursion in Algorithms",
    "subject": "Digital Solutions",
    "difficulty": "hard",
    "questions": [
        {
            "question": "What is the base case in a recursive function?",
            "answers": [
                {"id": "a", "text": "The first call to the function", "correct": False},
                {"id": "b", "text": "The condition that stops the recursion", "correct": True},
                {"id": "c", "text": "The return type of the function", "correct": False},
                {"id": "d", "text": "The recursive call inside the function", "correct": False},
            ],
            "explanation": "The base case is a condition where the function stops calling itself, preventing infinite recursion.",
        },
        {
            "question": "What happens if a recursive function has no base case?",
            "answers": [
                {"id": "a", "text": "It returns None automatically", "correct": False},
                {"id": "b", "text": "It runs exactly twice", "correct": False},
                {"id": "c", "text": "It causes a stack overflow error", "correct": True},
                {"id": "d", "text": "It compiles but never executes", "correct": False},
            ],
            "explanation": "Without a base case, the function calls itself indefinitely until the call stack is exhausted, causing a stack overflow.",
        },
    ],
}


def _bootstrap_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
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
        """
    )

    now = datetime.now(timezone.utc).isoformat()

    for uid, name, role in DEMO_USERS:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, name, role, created_at) VALUES (?, ?, ?, ?)",
            (uid, name, role, now),
        )

    for sid, name in DEMO_SUBJECTS:
        conn.execute(
            "INSERT OR IGNORE INTO subjects (id, name, active) VALUES (?, ?, 1)",
            (sid, name),
        )

    # Seed sample approved content if DB is fresh
    existing = conn.execute("SELECT COUNT(*) FROM content_items").fetchone()[0]
    if existing == 0:
        _seed_sample_content(conn, now)

    conn.commit()
    conn.close()


def _seed_sample_content(conn: sqlite3.Connection, now: str) -> None:
    def insert_quiz(data: dict, creator: int, subject_id: int, status: str) -> None:
        cur = conn.execute(
            """INSERT INTO content_items
               (created_by, subject_id, topic, difficulty, content_type, status,
                reviewed_by, reviewed_at, created_at, raw_json)
               VALUES (?, ?, ?, ?, 'quiz', ?, ?, ?, ?, ?)""",
            (
                creator,
                subject_id,
                data["topic"],
                data["difficulty"],
                status,
                2 if status == "approved" else None,
                now if status == "approved" else None,
                now,
                json.dumps(data),
            ),
        )
        cid = cur.lastrowid
        for i, q in enumerate(data["questions"]):
            conn.execute(
                """INSERT INTO quiz_questions
                   (content_id, question_order, question, options_json, explanation)
                   VALUES (?, ?, ?, ?, ?)""",
                (cid, i, q["question"], json.dumps(q["answers"]), q["explanation"]),
            )

    def insert_flashcard(data: dict, creator: int, subject_id: int, status: str) -> None:
        cur = conn.execute(
            """INSERT INTO content_items
               (created_by, subject_id, topic, difficulty, content_type, status,
                reviewed_by, reviewed_at, created_at, raw_json)
               VALUES (?, ?, ?, ?, 'flashcard', ?, ?, ?, ?, ?)""",
            (
                creator,
                subject_id,
                data["topic"],
                data["difficulty"],
                status,
                2 if status == "approved" else None,
                now if status == "approved" else None,
                now,
                json.dumps(data),
            ),
        )
        cid = cur.lastrowid
        for i, fc in enumerate(data["flashcards"]):
            conn.execute(
                """INSERT INTO flashcards
                   (content_id, card_order, front, back, card_type, tags_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    i,
                    fc["front"],
                    fc["back"],
                    fc.get("type", "summary"),
                    json.dumps(fc.get("tags", [])),
                ),
            )

    insert_quiz(SAMPLE_QUIZ_1, creator=2, subject_id=1, status="approved")
    insert_flashcard(SAMPLE_FLASHCARDS, creator=2, subject_id=1, status="approved")
    insert_quiz(SAMPLE_QUIZ_2, creator=2, subject_id=1, status="approved")
    insert_quiz(SAMPLE_PENDING_QUIZ, creator=1, subject_id=1, status="pending")


_bootstrap_db()


# ─── DB helpers ──────────────────────────────────────────────────────────────


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
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def check_role(user_id: int, *roles: str) -> tuple[dict | None, Any]:
    user = get_user(user_id)
    if not user:
        return None, (jsonify({"error": "User not found"}), 404)
    if user["role"] not in roles:
        return None, (jsonify({"error": f"Access denied. Requires role: {' or '.join(roles)}"}), 403)
    return user, None


# ─── Routes ──────────────────────────────────────────────────────────────────


@app.route("/")
def home() -> str:
    return render_template("index.html", model=MODEL, demo_users=DEMO_USERS)


@app.route("/api/subjects", methods=["GET"])
def list_subjects() -> Any:
    rows = get_db().execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/subjects", methods=["POST"])
def create_subject() -> Any:
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    user, err = check_role(user_id, "admin")
    if err:
        return err

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
def update_subject(sid: int) -> Any:
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    user, err = check_role(user_id, "admin")
    if err:
        return err

    db = get_db()
    if "active" in data:
        db.execute(
            "UPDATE subjects SET active = ? WHERE id = ?",
            (1 if data["active"] else 0, sid),
        )
        db.commit()
    row = db.execute("SELECT * FROM subjects WHERE id = ?", (sid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)


@app.route("/api/users", methods=["GET"])
def list_users() -> Any:
    user_id = int(request.args.get("user_id", 0))
    _, err = check_role(user_id, "admin")
    if err:
        return err
    rows = get_db().execute("SELECT id, name, role, created_at FROM users ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/users/<int:uid>/role", methods=["PATCH"])
def update_user_role(uid: int) -> Any:
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    _, err = check_role(user_id, "admin")
    if err:
        return err

    new_role = data.get("role", "")
    if new_role not in ("student", "teacher", "admin"):
        return jsonify({"error": "Invalid role. Must be student, teacher, or admin"}), 400

    db = get_db()
    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, uid))
    db.commit()
    row = db.execute("SELECT id, name, role FROM users WHERE id = ?", (uid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)


@app.route("/api/generate", methods=["POST"])
def generate_content() -> Any:
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "OPENROUTER_API_KEY is not configured. Add it to your .env file."}), 500

    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    user, err = check_role(user_id, "student", "teacher", "admin")
    if err:
        return err

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
        sub = get_db().execute("SELECT name FROM subjects WHERE id = ?", (subject_id,)).fetchone()
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
            (user_id, subject_id, topic, difficulty, content_type, now, json.dumps(parsed)),
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
        return jsonify({"error": "OpenRouter request failed", "details": resp.text}), resp.status_code
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": "Invalid AI response format", "details": str(exc)}), 502
    except requests.RequestException as exc:
        return jsonify({"error": "Network error calling OpenRouter", "details": str(exc)}), 502


@app.route("/api/content", methods=["GET"])
def list_content() -> Any:
    user_id = int(request.args.get("user_id", 0))
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    filters: list[str] = []
    params: list[Any] = []

    if user["role"] == "student":
        filters.append("(ci.status = 'approved' OR ci.created_by = ?)")
        params.append(user_id)

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

    where = "WHERE " + " AND ".join(filters) if filters else ""

    rows = get_db().execute(
        f"""SELECT ci.id, ci.topic, ci.difficulty, ci.content_type, ci.status,
                   ci.created_at, ci.reviewed_at, ci.subject_id,
                   u.name AS creator_name, ci.created_by,
                   s.name AS subject_name,
                   ru.name AS reviewer_name
            FROM content_items ci
            JOIN users u ON ci.created_by = u.id
            LEFT JOIN subjects s ON ci.subject_id = s.id
            LEFT JOIN users ru ON ci.reviewed_by = ru.id
            {where}
            ORDER BY ci.id DESC LIMIT 100""",
        params,
    ).fetchall()

    db = get_db()
    result = []
    for row in rows:
        item = dict(row)
        tbl = "quiz_questions" if item["content_type"] == "quiz" else "flashcards"
        count = db.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE content_id = ?", (item["id"],)
        ).fetchone()[0]
        item["item_count"] = count
        result.append(item)

    return jsonify(result)


@app.route("/api/content/<int:cid>", methods=["GET"])
def get_content(cid: int) -> Any:
    user_id = int(request.args.get("user_id", 0))
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

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

    if user["role"] == "student" and item["status"] != "approved" and item["created_by"] != user_id:
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
                (user_id, qd["id"]),
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
def update_content_status(cid: int) -> Any:
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    _, err = check_role(user_id, "teacher", "admin")
    if err:
        return err

    new_status = data.get("status")
    if new_status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "Invalid status. Must be approved, rejected, or pending"}), 400

    db = get_db()
    db.execute(
        "UPDATE content_items SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
        (new_status, user_id, datetime.now(timezone.utc).isoformat(), cid),
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


@app.route("/api/answer", methods=["POST"])
def submit_answer() -> Any:
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id", 0))
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

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
        (user_id, question_id, selected_option, 1 if is_correct else 0, datetime.now(timezone.utc).isoformat()),
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
def get_progress() -> Any:
    user_id = int(request.args.get("user_id", 0))
    if not get_user(user_id):
        return jsonify({"error": "User not found"}), 404

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
           GROUP BY ci.subject_id""",
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
def get_stats() -> Any:
    user_id = int(request.args.get("user_id", 0))
    _, err = check_role(user_id, "admin", "teacher")
    if err:
        return err

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
           GROUP BY ur.user_id ORDER BY attempts DESC LIMIT 5""",
    ).fetchall()

    return jsonify(
        {
            "total_users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "total_content": db.execute("SELECT COUNT(*) FROM content_items").fetchone()[0],
            "total_responses": db.execute("SELECT COUNT(*) FROM user_responses").fetchone()[0],
            "content_by_status": [dict(r) for r in by_status],
            "content_by_type": [dict(r) for r in by_type],
            "content_by_subject": [dict(r) for r in by_subject],
            "top_students": [dict(r) for r in top_students],
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
