# MySlates Offline Sync Middleware

A production-ready Django middleware service that queues offline operations and syncs them to the MySlates backend when connectivity is restored.

---

## Overview

MySlates operates in environments where internet connectivity is unreliable. This middleware sits between the client app and the Django backend, ensuring that any data created or modified while offline is reliably synced when the user comes back online.

```
Client App
    ↕
Sync Middleware  ← this service
    ↕
MySlates Django Backend
```

---

## Features

- **Offline queue** — operations are persisted to a local database when the backend is unreachable
- **Automatic sync** — Celery workers flush the queue every 60 seconds
- **Conflict resolution** — last-write-wins strategy with timestamp comparison
- **Idempotency** — duplicate operations are detected and skipped automatically
- **Retry logic** — failed operations are retried up to 5 times with exponential backoff
- **Dead letter queue** — operations that exhaust retries are flagged for manual review
- **Audit logging** — every sync attempt is logged with status and duration
- **JWT authentication** — authenticates with the MySlates backend using SimpleJWT

---

## Tech Stack

- **Python 3.12**
- **Django 5.0**
- **Django REST Framework**
- **Celery + Redis** — async task queue
- **SQLite** (dev) / **PostgreSQL** (production)
- **Firebase Admin SDK** — optional Firestore integration

---

## Project Structure

```
sync_middleware/
├── api/                    # REST API endpoints (submit, bulk, status)
├── client/                 # JavaScript client SDK (SyncMiddleware.js)
├── config/                 # Firebase config
├── core/                   # Django project settings, urls, celery
├── engine/                 # Sync engine, conflict resolver, idempotency
├── queue_app/              # SyncOperation and SyncLog models
├── tasks/                  # Celery async tasks
├── tests/                  # Test suite
├── utils/                  # Logger, exceptions, Django API client
├── .env.example            # Environment variable template
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Redis (for Celery)
- PostgreSQL (for production)

### Installation

```bash
# Clone the repo
git clone https://github.com/Shakurrrr/Myslates_Middleware.git
cd Myslates_Middleware

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### Environment Variables

Edit `.env` with your values:

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True

# MySlates Backend
DJANGO_API_BASE_URL=http://localhost:8000/api/v1
MYSLATES_SERVICE_EMAIL=middleware@myslates.com
MYSLATES_SERVICE_PASSWORD=your-service-account-password

# Redis
REDIS_URL=redis://localhost:6379/0

# Firebase (optional)
FIREBASE_CREDENTIALS_PATH=./serviceAccountKey.json

# Sync Settings
SYNC_MAX_RETRIES=5
SYNC_BATCH_SIZE=100
```

### Run Migrations

```bash
python manage.py makemigrations queue_app
python manage.py migrate
```

### Start the Server

```bash
python manage.py runserver
```

### Start Celery Worker

```bash
celery -A core worker --beat --loglevel=info
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sync/submit/` | Submit a single offline operation |
| POST | `/api/sync/bulk/` | Submit multiple offline operations at once |
| GET | `/api/sync/status/?op_ids=...` | Check sync status of operations |

### Submit a Single Operation

```bash
curl -X POST http://localhost:8000/api/sync/submit/ \
  -H "Content-Type: application/json" \
  -d '{
    "operation_type": "CREATE",
    "collection": "attendance",
    "document_id": "unique-doc-id",
    "payload": {
      "legacy_student_id": "MS613085",
      "status": "present",
      "marked_at": "2026-06-08T10:00:00Z"
    },
    "client_timestamp": "2026-06-08T10:00:00Z",
    "idempotency_key": "unique-key-per-operation",
    "user_id": "firebase-uid"
  }'
```

### Bulk Submit (after offline period)

```bash
curl -X POST http://localhost:8000/api/sync/bulk/ \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      { "operation_type": "CREATE", "collection": "attendance", ... },
      { "operation_type": "UPDATE", "collection": "assignments", ... }
    ]
  }'
```

---

## Supported Collections

| Collection | MySlates Endpoint |
|------------|-------------------|
| `schools` | `/academics/schools/` |
| `classes` | `/academics/classes/` |
| `subjects` | `/academics/subjects/` |
| `topics` | `/academics/topics/` |
| `assignments` | `/assignments/` |
| `submissions` | `/assignments/submissions/` |
| `attendance` | `/attendance/` |
| `users` | `/auth/users/` |
| `students` | `/auth/students/` |
| `teachers` | `/auth/teachers/` |
| `chats` | `/chat/chats/` |
| `messages` | `/chat/messages/` |
| `discussions` | `/chat/discussions/` |
| `announcements` | `/communication/announcements/` |
| `results` | `/communication/results/` |
| `notifications` | `/communication/notifications/` |
| `achievements` | `/gamification/achievements/` |
| `games` | `/gamification/games/` |
| `fees` | `/modules/fees/` |
| `cbt_exams` | `/modules/cbt-exams/` |
| `video_classes` | `/modules/video-classes/` |

---

## Operation Types

| Type | Description |
|------|-------------|
| `CREATE` | Creates a new record in the backend |
| `UPDATE` | Updates an existing record (partial update) |
| `DELETE` | Deletes a record from the backend |

---

## Operation Status Flow

```
pending → in_flight → synced
                   ↘ failed → (retry) → dead
```

| Status | Description |
|--------|-------------|
| `pending` | Waiting to be processed |
| `in_flight` | Currently being synced |
| `synced` | Successfully written to backend |
| `failed` | Failed, will be retried |
| `dead` | Retries exhausted, needs manual review |

---

## Client SDK

Drop `client/SyncMiddleware.js` into your web app. It detects online/offline state automatically and flushes the queue when connectivity is restored.

```javascript
const sync = new SyncMiddleware("https://your-middleware-url.com/api", userToken);

// Use this instead of direct API calls
await sync.write({
  operation_type:   "CREATE",
  collection:       "attendance",
  document_id:      crypto.randomUUID(),
  payload:          { legacy_student_id: "MS613085", status: "present" },
  client_timestamp: new Date().toISOString(),
});
```

---

## Payload Field Reference

When submitting operations, use the MySlates backend field names exactly:

### Attendance
```json
{
  "legacy_student_id": "MS613085",
  "legacy_teacher_id": "TCH001",
  "legacy_class_ref":  "CLS001",
  "status":            "present",
  "marked_at":         "2026-06-08T10:00:00Z"
}
```

### Assignment Submission
```json
{
  "assignment": 1,
  "answer":     "Student answer here",
  "image":      null
}
```

---

## Running Tests

```bash
python manage.py test
```

---

## Environment Notes

- `serviceAccountKey.json` is **never committed** to this repo — keep it local
- Use `.env` for all secrets — never hardcode credentials
- Switch `DATABASES` in `core/settings.py` to PostgreSQL before deploying to production

---

## Related Repositories

- [MySlates Backend](https://github.com/surajsadiqsalihu-wq/myslates_offline) — Django REST API by Sadik

---

## Author

Built by **Shehu (Shakur)** — DevOps & Cloud Engineer
