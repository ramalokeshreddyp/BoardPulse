<div align="center">

# ⚡ BoardPulse

### Real-Time Collaborative Task Board

**Django · Channels · Redis · PostgreSQL · Docker**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

> A production-ready, fully containerized Kanban board where every card move, presence join, and status update is broadcast to all connected users **instantly** — no page refresh, no polling.

[🚀 Quick Start](#-quick-start) · [📐 Architecture](#-architecture) · [📡 WebSocket Protocol](#-websocket-protocol) · [📊 Benchmarking](#-benchmarking) · [🔌 API Reference](#-api-reference)

---

</div>

## 📋 Table of Contents

- [Overview](#-overview)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Execution Flow](#-execution-flow)
- [Quick Start](#-quick-start)
- [Setup & Installation](#-setup--installation)
- [API Reference](#-api-reference)
- [WebSocket Protocol](#-websocket-protocol)
- [Benchmarking](#-benchmarking)
- [Test Credentials](#-test-credentials)
- [Troubleshooting](#-troubleshooting)

---

## 🌟 Overview

BoardPulse is a **real-time collaborative task management board** built on Django Channels and the ASGI paradigm. It demonstrates the architectural shift from Django's traditional synchronous WSGI model to an **event-driven, asynchronous architecture** capable of managing thousands of persistent WebSocket connections.

### Key Highlights

| Feature | Description |
|---|---|
| 🔄 **Real-Time Sync** | Task moves broadcast instantly to all connected clients via Redis pub/sub |
| 👥 **Live Presence** | See who's on the board right now — join/leave events in real-time |
| 🔐 **Secure WS** | Unauthenticated connections rejected with WebSocket close code `4001` |
| 🐳 **One-Command Deploy** | Full stack via `docker-compose up --build` |
| ⚡ **ASGI Native** | Daphne ASGI server handles HTTP and WebSocket on the same port |
| 🎯 **Zero JS Framework** | Pure browser WebSocket API + HTML5 Drag and Drop |

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Language** | Python 3.11 | Modern async support, type hints |
| **Web Framework** | Django 4.2 | Battle-tested ORM, auth, admin |
| **Real-Time** | Django Channels 4.1 | ASGI WebSocket consumer framework |
| **ASGI Server** | Daphne 4.1 | Official Django Channels ASGI server |
| **Message Broker** | Redis 7 | Fast pub/sub channel layer backend |
| **Database** | PostgreSQL 15 | Robust relational DB for task persistence |
| **REST API** | Django REST Framework 3.15 | Serializers, auth, viewsets |
| **Containerization** | Docker + Compose | Reproducible, isolated environments |
| **Presence Cache** | Django Redis Cache | Shared state across consumer instances |

---

## 📐 Architecture

### System Overview

```mermaid
graph TB
    subgraph Browser["🌐 Client Browser"]
        UI[Kanban Board UI]
        JS[Native WebSocket API]
        DND[HTML5 Drag & Drop]
    end

    subgraph Docker["🐳 Docker Compose Stack"]
        subgraph Web["web (Daphne ASGI)"]
            ASGI[ProtocolTypeRouter]
            HTTP[Django Views / DRF]
            WS[AuthMiddlewareStack]
            Consumer[BoardConsumer]
        end
        subgraph DB["db (PostgreSQL 15)"]
            PG[(postgres)]
        end
        subgraph Cache["redis (Redis 7)"]
            CL[Channel Layer]
            PR[Presence Store]
        end
    end

    UI -->|drag & drop| DND
    DND -->|ws.send JSON| JS
    JS <-->|WebSocket /ws/board/1/| ASGI
    ASGI -->|HTTP| HTTP
    ASGI -->|WebSocket| WS
    WS --> Consumer
    Consumer -->|database_sync_to_async| PG
    Consumer -->|group_send| CL
    CL -->|broadcast| Consumer
    Consumer -->|presence set| PR
    HTTP -->|ORM| PG
```

### Data Flow — Task Move

```mermaid
sequenceDiagram
    participant A as Client A (Browser)
    participant B as Client B (Browser)
    participant C as BoardConsumer
    participant DB as PostgreSQL
    participant R as Redis

    A->>C: WS: {"action":"move_task","task_id":1,"new_status":"done"}
    C->>DB: database_sync_to_async → Task.objects.get(1).save()
    DB-->>C: Updated task
    C->>R: channel_layer.group_send("board_1", {type:"task.moved",...})
    R-->>C: Broadcast to all consumers in group
    C-->>A: WS: {"type":"task.moved","task_id":1,"new_status":"done","moved_by":"user1@..."}
    C-->>B: WS: {"type":"task.moved","task_id":1,"new_status":"done","moved_by":"user1@..."}
    A->>A: DOM: move card to Done column
    B->>B: DOM: move card to Done column
```

### Presence Tracking Flow

```mermaid
sequenceDiagram
    participant A as User A (Browser)
    participant B as User B (Browser)
    participant CA as Consumer A
    participant CB as Consumer B
    participant R as Redis Cache

    A->>CA: WebSocket connect /ws/board/1/
    CA->>R: presence_add("board_1", "user_a@...")
    CA->>R: group_send → presence join
    R-->>CA: broadcast
    CA-->>A: {"type":"presence","payload":{"action":"join","online_users":["user_a"]}}

    B->>CB: WebSocket connect /ws/board/1/
    CB->>R: presence_add("board_1", "user_b@...")
    CB->>R: group_send → presence join
    R-->>CA: broadcast
    R-->>CB: broadcast
    CA-->>A: {"type":"presence","payload":{"action":"join","online_users":["user_a","user_b"]}}
    CB-->>B: {"type":"presence","payload":{"action":"join","online_users":["user_a","user_b"]}}

    A--xCA: disconnect
    CA->>R: presence_remove("board_1", "user_a@...")
    CA->>R: group_send → presence leave
    R-->>CB: broadcast
    CB-->>B: {"type":"presence","payload":{"action":"leave","online_users":["user_b"]}}
```

---

## 📁 Project Structure

```
BoardPulse/
│
├── 📄 README.md                    # This file
├── 📄 architecture.md              # Deep architecture documentation
├── 📄 projectdocumentation.md      # Full project documentation
├── 📄 docker-compose.yml           # Service orchestration
├── 🐳 Dockerfile                   # Multi-stage container build
├── 📄 entrypoint.sh                # Container startup (migrate→seed→serve)
├── 📄 manage.py                    # Django CLI
├── 📄 requirements.txt             # Python dependencies
├── 📄 .env.example                 # Environment variable template
├── 📄 .env                         # Local environment (gitignored)
├── 📄 submission.json              # Test credentials
│
├── 📦 taskboard/                   # Django project package
│   ├── __init__.py
│   ├── settings.py                 # All configuration (DB, Redis, Channels)
│   ├── asgi.py                     # ASGI entry point (ProtocolTypeRouter)
│   ├── urls.py                     # Root URL routing
│   └── wsgi.py                     # WSGI fallback
│
├── 📦 core/                        # Main application
│   ├── models.py                   # Board, Task models
│   ├── consumers.py                # ⚡ BoardConsumer (WebSocket logic)
│   ├── routing.py                  # WebSocket URL patterns
│   ├── serializers.py              # DRF serializers
│   ├── views.py                    # REST API views
│   ├── urls.py                     # API URL patterns (/api/...)
│   ├── page_urls.py                # Page URL patterns
│   ├── page_views.py               # HTML-rendering views
│   ├── admin.py                    # Django admin registration
│   ├── apps.py                     # App configuration
│   ├── migrations/                 # Database migrations
│   └── management/
│       └── commands/
│           └── seed_db.py          # Database seeding command
│
├── 🎨 templates/core/              # HTML templates
│   ├── board.html                  # Kanban board (WS + DnD)
│   ├── board_list.html             # Board listing page
│   └── login.html                  # Authentication page
│
├── 🎨 static/css/
│   └── style.css                   # Dark glassmorphism design system
│
└── 📊 scripts/
    └── benchmark.py                # WebSocket load testing script
```

---

## 🔄 Execution Flow

### Application Startup

```mermaid
flowchart TD
    A([docker-compose up --build]) --> B[Build Docker image\nmulti-stage]
    B --> C{db healthy?\npg_isready}
    C -- No --> C
    C -- Yes --> D{redis healthy?\nredis-cli ping}
    D -- No --> D
    D -- Yes --> E[entrypoint.sh]
    E --> F[python manage.py migrate]
    F --> G[python manage.py seed_db]
    G --> H[python manage.py collectstatic]
    H --> I[daphne -b 0.0.0.0 -p 8000\ntaskboard.asgi:application]
    I --> J([App ready at localhost:8000])
```

### WebSocket Connection Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Connecting: Browser opens WS
    Connecting --> Authenticating: HTTP Upgrade
    Authenticating --> Rejected: user not authenticated\nclose(4001)
    Authenticating --> JoiningGroup: authenticated
    JoiningGroup --> Active: channel_layer.group_add\n+ accept()
    Active --> Active: receive move_task\n→ DB update\n→ group_send
    Active --> Active: receive presence join/leave\n→ group_send
    Active --> Leaving: disconnect()
    Leaving --> [*]: group_discard\n+ presence_remove\n+ broadcast leave
    Rejected --> [*]
```

### Request Routing

```mermaid
flowchart LR
    REQ([Incoming Request]) --> ASGI[ProtocolTypeRouter]
    ASGI -->|protocol=http| DJANGO[Django ASGI Handler]
    ASGI -->|protocol=websocket| AUTH[AuthMiddlewareStack]
    DJANGO --> URLS[URL Router]
    URLS -->|/api/...| DRF[DRF ViewSets]
    URLS -->|/boards/...| VIEWS[Page Views]
    URLS -->|/login/| LOGIN[Auth Views]
    AUTH --> WSROUTER[WebSocket URLRouter]
    WSROUTER -->|/ws/board/id/| CONSUMER[BoardConsumer]
    DRF --> ORM[Django ORM]
    VIEWS --> ORM
    CONSUMER --> ORM
    ORM --> PG[(PostgreSQL)]
    CONSUMER --> REDIS[(Redis)]
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### One-command launch

```bash
git clone https://github.com/ramalokeshreddyp/BoardPulse.git
cd BoardPulse
cp .env.example .env
docker-compose up --build
```

Open **http://localhost:8000** — login, open a second tab, and drag cards to see real-time sync.

---

# Note on Hosting

This repository includes a static `docs/` folder previously used for a GitHub Pages site. The production realtime application requires a backend (Django, Redis, PostgreSQL) and must be deployed to a container host or managed platform (Render, Fly.io, Railway, DigitalOcean, etc.).
---

## ⚙️ Setup & Installation

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/ramalokeshreddyp/BoardPulse.git
cd BoardPulse

# 2. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work out of the box)

# 3. Start all services
docker-compose up --build -d

# 4. Check health status
docker-compose ps
# All three containers should show "healthy"

# 5. View logs
docker-compose logs -f web

# 6. Open application
# http://localhost:8000
```

### Option B: Local Development (without Docker)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL and Redis locally, then configure .env:
export DATABASE_URL=postgres://postgres:postgres@localhost:5432/taskboard
export REDIS_URL=redis://localhost:6379/0
export SECRET_KEY=local-dev-secret-key

# 4. Run migrations and seed
python manage.py migrate
python manage.py seed_db

# 5. Start ASGI server
daphne -b 0.0.0.0 -p 8000 taskboard.asgi:application
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key | — (required) |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://postgres:postgres@db:5432/taskboard` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `POSTGRES_DB` | Database name | `taskboard` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | `postgres` |
| `WEB_PORT` | Host port for web service | `8000` |

---

## 🔌 API Reference

All endpoints require authentication (session cookie or HTTP Basic Auth).

### Authentication

```bash
# Login via Basic Auth (for API testing)
curl -u user1:password123 http://localhost:8000/api/me/
```

### Boards

```bash
# List all boards
GET /api/boards/

curl -u user1:password123 http://localhost:8000/api/boards/

# Create a board
POST /api/boards/
Content-Type: application/json
{"name": "My Board"}

curl -X POST http://localhost:8000/api/boards/ \
  -u user1:password123 \
  -H "Content-Type: application/json" \
  -d '{"name":"Sprint Board"}'
# → 201 Created
```

### Tasks

```bash
# List tasks for a board
GET /api/boards/{board_id}/tasks/

# Create a task
POST /api/boards/{board_id}/tasks/
Content-Type: application/json
{"title": "New feature", "status": "todo"}

curl -X POST http://localhost:8000/api/boards/1/tasks/ \
  -u user1:password123 \
  -H "Content-Type: application/json" \
  -d '{"title":"Implement login","status":"in_progress"}'
# → 201 Created
```

### Response Schemas

**Board:**
```json
{
  "id": 1,
  "name": "Project Alpha",
  "owner": {"id": 1, "username": "user1", "email": "user1@example.com"},
  "task_count": 5,
  "created_at": "2026-05-06T12:00:00Z"
}
```

**Task:**
```json
{
  "id": 1,
  "title": "Design database schema",
  "description": "...",
  "board": 1,
  "status": "todo",
  "assigned_to": null,
  "created_at": "2026-05-06T12:00:00Z",
  "updated_at": "2026-05-06T12:00:00Z"
}
```

---

## 📡 WebSocket Protocol

### Connect

```
ws://localhost:8000/ws/board/{board_id}/
```

> Requires session cookie. Unauthenticated → close code **4001**

### Messages

**Client → Server**

```json
// Move a task
{"action": "move_task", "task_id": 1, "new_status": "in_progress"}

// Ping (latency test)
{"action": "ping", "timestamp": 1234567890.123}
```

Valid statuses: `"todo"` · `"in_progress"` · `"done"`

**Server → Client**

```json
// Task moved broadcast
{
  "type": "task.moved",
  "task_id": 1,
  "new_status": "in_progress",
  "moved_by": "user1@example.com"
}

// Presence update
{
  "type": "presence",
  "payload": {
    "action": "join",
    "user": "user2@example.com",
    "online_users": ["user1@example.com", "user2@example.com"]
  }
}

// Pong
{"type": "pong", "timestamp": 1234567890.123}

// Error
{"type": "error", "message": "Invalid task_id or new_status"}
```

---

## 📊 Benchmarking

Install benchmark dependencies (outside container):

```bash
pip install websockets aiohttp
```

### Run load test

```bash
# 10 concurrent clients, 10 seconds
python scripts/benchmark.py --clients 10 --board-id 1

# 50 clients, 30 seconds, custom URL
python scripts/benchmark.py --clients 50 --board-id 1 --duration 30 --url http://localhost:8000

# Custom send interval (0.5s per client)
python scripts/benchmark.py --clients 20 --board-id 1 --duration 20 --interval 0.5
```

### All Options

| Flag | Default | Description |
|---|---|---|
| `--url` | `http://localhost:8000` | Server base URL |
| `--board-id` | `1` | Board to connect to |
| `--clients` | `10` | Concurrent WebSocket clients |
| `--duration` | `10` | Test duration per client (seconds) |
| `--interval` | `1.0` | Send interval per client (seconds) |
| `--username` | `user1@example.com` | Auth username or email |
| `--password` | `password123` | Auth password |

### Sample Output

```
════════════════════════════════════════════════════════════
TaskBoard WebSocket Benchmark Results
================================================================
Board ID              : 1
Concurrent clients    : 10
Duration              : 10s
Send interval         : 1.00s
Elapsed               : 12.43s
Connection success    : 10/10 (100.0%)
Messages sent         : 100
Messages received     : 950
Broadcast latency (move_task -> task.moved):
  Average             : 4.21 ms
  Median              : 3.87 ms
  P95                 : 9.14 ms
  P99                 : 15.32 ms
  Max                 : 28.45 ms
  Samples             : 100
```

### The Blocking Experiment

To understand `async`/`await` at a deep level, try this in `core/consumers.py`:

```python
# In the receive() method — BLOCKING (bad!)
import time
time.sleep(2)   # All 5 clients freeze for 2 seconds

# vs. NON-BLOCKING (correct)
import asyncio
await asyncio.sleep(2)   # Only this consumer pauses; others stay responsive
```

Run `python scripts/benchmark.py --clients 5 --board-id 1` under each and observe the difference.

---

## 🔑 Test Credentials

| Username | Email | Password |
|---|---|---|
| `user1` | `user1@example.com` | `password123` |
| `user2` | `user2@example.com` | `password123` |

Created automatically by `manage.py seed_db` on container startup.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| Containers not starting | Run `docker-compose logs db` — wait for `pg_isready` |
| WS closes immediately | Ensure session cookie is sent; check auth middleware |
| `4001` close code | You're not logged in — visit `/login/` first |
| Redis connection refused | Check `REDIS_URL` in `.env` matches service name |
| Static files 404 | Run `python manage.py collectstatic` inside container |
| Port 8000 in use | Change `WEB_PORT=8001` in `.env` |

### Useful Docker Commands

```bash
# View all container logs
docker-compose logs -f

# Shell into the web container
docker-compose exec web bash

# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d taskboard

# Check seeded data
docker-compose exec db psql -U postgres -d taskboard -c "SELECT * FROM core_task;"

# Restart just the web service
docker-compose restart web

# Full clean reset
docker-compose down -v && docker-compose up --build
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ⚡ Django Channels · Engineered for real-time collaboration**

[⬆ Back to top](#-boardpulse)

</div>
