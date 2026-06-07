# DigiClass — Learning Platform

DigiClass is a classroom learning platform where teachers and students build a
shared library of practice **quizzes** and **flashcards**. Content can be
drafted with AI assistance, is reviewed and approved by teachers, and students
practise against it while their progress is tracked over time.

- 🔐 **Session-based authentication** with hashed passwords and role-based access
- 👩‍🏫 **Three roles** — students, teachers, and admins — each with a tailored dashboard
- 📚 **Content library** of teacher-approved quizzes and flashcard sets
- 🎯 **Practice mode** with instant feedback, scoring, and progress analytics
- ✨ **Optional AI generation** of new content via OpenRouter
- 🗄️ **Zero-config storage** using SQLite

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit SECRET_KEY (and OPENROUTER_API_KEY if desired)
python app.py
```

Open **http://127.0.0.1:5000** — you'll land on the sign-in page. On first run
the database is created and seeded with a realistic demonstration dataset
(members, subjects, content, and practice history).

### Demo accounts

All seeded accounts share the password **`Learn2024!`**. The sign-in page also
has one-click buttons for each role.

| Role    | Email                                   |
| ------- | --------------------------------------- |
| Student | `hamish.reid@student.digiclass.edu`     |
| Teacher | `a.morgan@digiclass.edu`                |
| Admin   | `r.calloway@digiclass.edu`              |

You can also **register** a new account from the sign-in page; new users join as
students, and an admin can promote them from the **Users** panel.

## Running in production

The app is a standard WSGI application served via **gunicorn**:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export FLASK_DEBUG=0
export SESSION_COOKIE_SECURE=1          # when behind HTTPS
gunicorn app:app --bind 0.0.0.0:8000 --workers 2
```

A `Procfile` is included for platforms like Heroku/Render/Railway.

> **Note:** this build uses SQLite, which is ideal for a single-node deployment.
> For multi-node scale, point `DATABASE_PATH` at a shared volume or migrate the
> schema in `app.py` to Postgres.

## Configuration

| Variable                | Default                        | Purpose                                            |
| ----------------------- | ------------------------------ | -------------------------------------------------- |
| `SECRET_KEY`            | random (dev only)              | Signs session cookies — **set a stable value**     |
| `DATABASE_PATH`         | `digiclass.db`                 | SQLite database file location                       |
| `OPENROUTER_API_KEY`    | _(empty)_                      | Enables AI content generation (optional)            |
| `OPENROUTER_MODEL`      | `google/gemini-2.5-flash-lite` | Model used for generation                           |
| `SESSION_COOKIE_SECURE` | `0`                            | Set `1` to require HTTPS for the session cookie     |
| `FLASK_DEBUG`           | `1`                            | Set `0` in production                               |

## Roles & permissions

| Capability                        | Student | Teacher | Admin |
| --------------------------------- | :-----: | :-----: | :---: |
| Browse & practise approved content|   ✅    |   ✅    |  ✅   |
| Draft content with AI             |   ✅    |   ✅    |  ✅   |
| View own pending drafts           |   ✅    |   ✅    |  ✅   |
| Review / approve / reject content |   ❌    |   ✅    |  ✅   |
| View dashboard & analytics        |   ❌    |   ✅    |  ✅   |
| Manage users & roles              |   ❌    |   ❌    |  ✅   |
| Manage subjects                   |   ❌    |   ❌    |  ✅   |

## Project layout

```
app.py              Flask app: auth, RBAC, REST API, page routes
seed.py             Idempotent demonstration-data seeder
templates/
  auth.html         Sign-in / registration page
  index.html        Main single-page application
static/
  styles.css        Styles
requirements.txt    Python dependencies
Procfile            Production process definition (gunicorn)
```

## Re-seeding the database

Seeding runs automatically when the database is empty. To rebuild from scratch:

```bash
rm digiclass.db
python seed.py        # or just start the app again
```

## Key API routes

All API routes require an authenticated session (cookie-based).

| Method & path                       | Access          | Description                          |
| ----------------------------------- | --------------- | ------------------------------------ |
| `POST /api/auth/register`           | public          | Create a student account             |
| `POST /api/auth/login` / `logout`   | public / auth   | Start / end a session                |
| `GET  /api/content`                 | auth            | List & filter library content        |
| `GET  /api/content/<id>`            | auth            | Full quiz / flashcard set            |
| `PATCH /api/content/<id>/status`    | teacher/admin   | Approve / reject / unpublish         |
| `POST /api/answer`                  | auth            | Submit a quiz answer                 |
| `GET  /api/progress`                | auth            | Personal progress analytics          |
| `GET  /api/stats`                   | teacher/admin   | Cohort dashboard                     |
| `POST /api/generate`                | auth            | AI-draft new content (if configured) |
| `GET/POST/PATCH /api/subjects`      | auth / admin    | Browse / manage subjects             |
| `GET  /api/users`, `PATCH .../role` | admin           | User & role management               |
| `GET  /health`                      | public          | Liveness probe                       |
