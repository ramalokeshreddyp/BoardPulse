# ⚡ TaskBoard — Real-Time Collaborative Task Board

> A fully functional, production-ready real-time collaborative Kanban board built with **Django Channels**, **WebSockets**, **PostgreSQL**, and **Redis**, containerized with **Docker Compose**.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Django](https://img.shields.io/badge/Django-4.2-green)
![Channels](https://img.shields.io/badge/Django%20Channels-4.1-purple)
![Redis](https://img.shields.io/badge/Redis-7-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [WebSocket Protocol](#websocket-protocol)
- [Benchmarking](#benchmarking)
- [Test Credentials](#test-credentials)

---

## Overview

TaskBoard demonstrates the transition from Django's traditional WSGI request-response model to the **ASGI event-driven paradigm** using Django Channels. Users can collaboratively manage tasks on a shared Kanban board, with changes broadcasting in real-time to all connected users.

**Key concepts demonstrated:**
- ASGI vs WSGI architectural difference
- `AsyncWebsocketConsumer` lifecycle (connect → receive → disconnect)
- Redis-backed channel layers for multi-process broadcasting
- `database_sync_to_async` adapter for safe async DB calls
- Live presence tracking across connected users
- HTML5 Drag-and-Drop without any frontend framework

---

## Architecture

```
Browser (Plain JS + HTML5 DnD)
        │  WebSocket /ws/board/{id}/
        ▼
Daphne ASGI Server (port 8000)
        │
        ├── HTTP  → Django Views / DRF REST API
        │
        └── WS   → AuthMiddlewareStack
                       └── BoardConsumer
                               │
                               ├── database_sync_to_async → PostgreSQL
                               │
                               └── channel_layer.group_send → Redis
                                       │
                                       └── Broadcast → All BoardConsumers
                                                           └── All WS Clients
```

### Data Flow (Task Move)
1. User drags a card → browser sends `move_task` JSON over WebSocket
2. `BoardConsumer.receive()` parses the message
3. `database_sync_to_async` updates task status in PostgreSQL
4. Consumer calls `channel_layer.group_send()` targeting `board_{id}` group
5. Redis broadcasts to all consumers subscribed to that group
6. Each consumer's `task_moved()` handler sends the update to its WebSocket client
7. Every browser updates its UI simultaneously

---

## Features

| Feature | Description |
|---|---|
| 🔐 WebSocket Authentication | Unauthenticated connections rejected with close code `4001` |
| 📡 Real-time Task Sync | Drag-and-drop task moves broadcast to all connected clients |
| 👥 Presence Tracking | Live "who's online" sidebar with join/leave notifications |
| 🗄️ REST API | Full CRUD for boards and tasks via DRF |
| 🐳 Docker Compose | Single command to start web + db + redis |
| 🔄 Auto-migrate & Seed | Container startup auto-runs migrations and seeds test data |
| 📊 Benchmark Script | Load test WebSocket server with configurable clients |
| 🎨 Modern UI | Dark glassmorphism Kanban design, no frontend framework |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Docker Engine + Compose)
- No local Python installation required for running via Docker

---

## Quick Start

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd Gpp-14
cp .env.example .env
```

### 2. Start all services

```bash
docker-compose up --build -d
```

This will:
- Build the Django application container
- Start PostgreSQL (waits for `pg_isready`)
- Start Redis (waits for `redis-cli ping`)
- Run `manage.py migrate`
- Run `manage.py seed_db` (creates test users, board, tasks)
- Start Daphne ASGI server on port 8000

### 3. Verify health

```bash
docker-compose ps
```

All three containers should show `healthy` within ~2 minutes.

### 4. Open the board

Navigate to [http://localhost:8000](http://localhost:8000)

Login with: `user1` / `password123`

Open another browser tab (or incognito) and login with: `user2` / `password123`

Navigate to the same board — **drag cards and watch them move in real-time!**

### 5. View logs

```bash
docker-compose logs -f web
```

### 6. Stop

```bash
docker-compose down
```

---

## Project Structure

```
Gpp-14/
├── taskboard/              # Django project
│   ├── settings.py         # All configuration
│   ├── asgi.py             # ASGI entry point (ProtocolTypeRouter)
│   └── urls.py             # Root URL config
├── core/                   # Main application
│   ├── models.py           # Board, Task models
│   ├── consumers.py        # WebSocket consumer (BoardConsumer)
│   ├── routing.py          # WebSocket URL patterns
│   ├── serializers.py      # DRF serializers
│   ├── views.py            # REST API views
│   ├── urls.py             # API URL patterns
│   ├── page_views.py       # HTML page views
│   └── management/
│       └── commands/
│           └── seed_db.py  # Database seeding command
├── templates/core/         # HTML templates
│   ├── board.html          # Kanban board (WebSocket + DnD)
│   ├── board_list.html     # Board listing page
│   └── login.html          # Authentication page
├── static/css/style.css    # Dark glassmorphism stylesheet
├── scripts/
│   └── benchmark.py        # WebSocket load testing script
├── Dockerfile              # Multi-stage container build
├── docker-compose.yml      # Service orchestration
├── entrypoint.sh           # Container startup script
├── .env.example            # Environment variable documentation
├── submission.json         # Test credentials
└── requirements.txt        # Python dependencies
```

---

## API Reference

All API endpoints require authentication (session cookie or HTTP Basic Auth).

### Boards

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/boards/` | List all boards |
| `POST` | `/api/boards/` | Create a new board |
| `GET` | `/api/boards/{id}/` | Get board details with tasks |

**Create Board:**
```bash
curl -X POST http://localhost:8000/api/boards/ \
  -u user1:password123 \
  -H "Content-Type: application/json" \
  -d '{"name": "My New Board"}'
```

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/boards/{id}/tasks/` | List tasks for a board |
| `POST` | `/api/boards/{id}/tasks/` | Create a task |
| `PATCH` | `/api/boards/{id}/tasks/{task_id}/` | Update a task |
| `DELETE` | `/api/boards/{id}/tasks/{task_id}/` | Delete a task |

**Create Task:**
```bash
curl -X POST http://localhost:8000/api/boards/1/tasks/ \
  -u user1:password123 \
  -H "Content-Type: application/json" \
  -d '{"title": "New feature", "status": "todo"}'
```

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/me/` | Current authenticated user |
| `POST` | `/login/` | Session login |
| `GET` | `/logout/` | Session logout |

---

## WebSocket Protocol

### Connection

```
ws://localhost:8000/ws/board/{board_id}/
```

Authentication is handled via Django session cookie. Unauthenticated connections are closed with **code 4001**.

### Client → Server Messages

**Move Task:**
```json
{
  "action": "move_task",
  "task_id": 1,
  "new_status": "in_progress"
}
```

Valid statuses: `"todo"`, `"in_progress"`, `"done"`

**Ping (latency test):**
```json
{
  "action": "ping",
  "timestamp": 1234567890.123
}
```

### Server → Client Messages

**Task Moved Broadcast:**
```json
{
  "type": "task.moved",
  "task_id": 1,
  "new_status": "in_progress",
  "moved_by": "user1@example.com"
}
```

**Presence Update:**
```json
{
  "type": "presence",
  "payload": {
    "action": "join",
    "user": "user2@example.com",
    "online_users": ["user1@example.com", "user2@example.com"]
  }
}
```

**Pong:**
```json
{
  "type": "pong",
  "timestamp": 1234567890.123
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Invalid task_id or new_status"
}
```

---

## Benchmarking

Install benchmark dependencies (outside Docker):
```bash
pip install websockets aiohttp
```

### Basic load test
```bash
python scripts/benchmark.py --clients 10 --board-id 1
```

### Full options
```bash
python scripts/benchmark.py \
  --url http://localhost:8000 \
  --board-id 1 \
  --clients 50 \
  --duration 15 \
  --username user1 \
  --password password123
```

### Ping/pong latency mode
```bash
python scripts/benchmark.py --clients 10 --board-id 1 --ping
```

### Sample output
```
════════════════════════════════════════════════════════════
  📊 BENCHMARK RESULTS
════════════════════════════════════════════════════════════
  Board ID     : 1
  Clients      : 10
  Duration     : 10s
  Total time   : 12.43s
────────────────────────────────────────────────────────────
  Connected    : 10/10 (100%)
  Messages sent: 100
  Messages recv: 950
────────────────────────────────────────────────────────────
  Latency (round-trip broadcast)
    Mean  : 4.21 ms
    Median: 3.87 ms
    P95   : 9.14 ms
    P99   : 15.32 ms
    Min   : 1.23 ms
    Max   : 28.45 ms
════════════════════════════════════════════════════════════
```

### The Blocking Experiment

To demonstrate how blocking calls freeze the async event loop:

1. **Add a blocking call** in `consumers.py` inside `receive()`:
   ```python
   import time
   time.sleep(2)  # BLOCKS the entire event loop!
   ```
   Run with 5 clients — all connections freeze for 2 seconds.

2. **Replace with async sleep**:
   ```python
   import asyncio
   await asyncio.sleep(2)  # Non-blocking — other clients stay responsive
   ```
   Now only the yielding consumer pauses; all others continue normally.

---

## Test Credentials

| Username | Email | Password |
|----------|-------|----------|
| `user1` | `user1@example.com` | `password123` |
| `user2` | `user2@example.com` | `password123` |

These are created automatically by the `seed_db` command on container startup.

---

## Key Implementation Details

### Why `database_sync_to_async`?

Django's ORM is synchronous. Calling it directly in an `async def` method would **block the entire event loop**, freezing all WebSocket connections on that server process. `database_sync_to_async` runs the ORM call in a thread pool, returning control to the event loop while the DB query executes.

### Why Redis for the Channel Layer?

A single consumer only knows about its own connected client. Redis acts as the **central message bus**: when one consumer calls `group_send()`, Redis broadcasts to all consumers in that group — even across multiple server processes or machines. This is what enables horizontal scaling.

### Presence Tracking

Online users per board are stored as Python `set` objects in the Redis cache (via Django's cache framework). When a user connects, their email is added to the set; on disconnect, it's removed. The updated list is then broadcast to all connected clients.
