# AI-Powered Chatbot System

A production-ready **Django REST API** backend for an AI-powered chatbot. Supports **Anthropic Claude**, **OpenAI GPT**, or a **built-in mock provider** for testing. JWT-authenticated, rate-limited, and fully documented with Swagger.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Assumptions](#assumptions)
- [Design Decisions](#design-decisions)

---

## Features

- 🤖 **Multi-provider AI** — swap between Anthropic Claude, OpenAI GPT, or Mock with a single env variable
- 🔐 **JWT Authentication** — secure register/login/refresh/logout flow
- 💬 **Persistent chat sessions** — full message history with a configurable context window
- 🛡️ **Rate limiting** — per-user request throttling on the message endpoint
- 📄 **Auto-documentation** — Swagger UI and ReDoc out of the box
- 🪵 **Structured JSON logging** — request/response and AI call logs ready for log aggregators
- ⚙️ **Layered settings** — separate development and production configs

---

## Architecture

```
┌─────────────────────────────────────────────┐
│               HTTP Clients                  │
└─────────────────┬───────────────────────────┘
                  │ REST (JSON)
┌─────────────────▼───────────────────────────┐
│              Views (API Layer)              │  ← Input validation, HTTP status codes
│         authentication/views.py             │
│         chat/views.py                       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│           Service Layer                     │  ← Business logic, orchestration
│         chat/services.py                    │
└──────────┬──────────────┬───────────────────┘
           │              │
┌──────────▼──────┐  ┌────▼────────────────────┐
│  Data Layer     │  │   AI Service Layer       │
│  (Django ORM)   │  │  ai_service/             │
│  chat/models.py │  │  providers.py            │
└─────────────────┘  └─────────────────────────┘
```

| Layer | Responsibility |
|-------|----------------|
| **Views** | Parse HTTP requests, validate input with serializers, call services, return responses |
| **Services** | Business logic — session lifecycle, message orchestration, context building |
| **AI Providers** | Abstracted LLM calls behind `BaseAIProvider`; swap providers without touching business logic |
| **Models** | Database schema for `ChatSession` and `Message` |
| **Core** | Shared utilities: custom exception handler, JSON logging, request middleware |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Django 4.2 + Django REST Framework 3.15 |
| Auth | JWT via `djangorestframework-simplejwt` |
| AI | Gemini(primary), OpenAI GPT (alternate), Mock (testing) |
| Database | Mysql (dev) / PostgreSQL (production) |
| Cache / Rate Limit | LocMemCache (dev) / Redis (production) |
| Docs | drf-yasg (Swagger UI + ReDoc) |

---

## Project Structure

```
AI-Powered-Chatbot-System/
├── ai_service/                # AnthropicProvider, OpenAIProvider, MockProvider
│   └── apps.py
│   └── providers.py           
├── aichatbotproject/          # Django project config
│   │   ├── settings.py        
│   │   ├── url.py              
│   │   └── wsgi.py      
│   └── urls.py
├── authentication/            # User registration, JWT auth, profile
│   ├── serializers.py
│   ├── apps.py
│   ├── views.py
│   └── urls.py
├── chat/                      # Sessions, messages, AI orchestration
│   ├── models.py              # ChatSession, Message
│   ├── admin.py    
│   ├── apps.py    
│   ├── serializers.py
│   ├── services.py            
│   ├── views.py               # Business logic
│   └── urls.py
├── core/
│   ├── exceptions/
│   │   └── handlers.py        # Custom exception handler + exception classes
│   └── utils/
│       ├── logging.py         # JSON log formatter
│       └── middleware.py      # Request/response logging middleware
├── logs/                      # Application log output
├── manage.py
├── requirements.txt
└── runtime.txt
```

---

## Setup Instructions

### Prerequisites

- Python 3.11+ (see `runtime.txt`)
- pip

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/tobintonye/AI-Powered-Chatbot-System.git
cd AI-Powered-Chatbot-System
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set your AI provider key
```

Minimum required for real AI responses:

```env
SECRET_KEY=your-django-secret-key
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

To run without an API key (returns canned responses):

```env
AI_PROVIDER=mock
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. (Optional) Create a superuser

```bash
python manage.py createsuperuser
```

### 6. Start the development server

```bash
python manage.py runserver
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000/api/` | API root |
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/admin/` | Django admin |

---

## API Reference

All responses follow a consistent envelope:

```json
// Success
{ "success": true, "data": { ... } }

// Error
{ "success": false, "error": { "code": "...", "message": "...", "details": {} } }
```

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register/` | Create a new account |
| `POST` | `/api/auth/token/` | Login → returns `access` + `refresh` tokens |
| `POST` | `/api/auth/token/refresh/` | Refresh an access token |
| `POST` | `/api/auth/logout/` | Invalidate a refresh token |
| `GET` | `/api/auth/me/` | Get current user profile |
| `PATCH` | `/api/auth/me/` | Update current user profile |

### Chat Sessions & Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/sessions/` | Create a new session |
| `GET` | `/api/chat/sessions/` | List all sessions |
| `GET` | `/api/chat/sessions/{id}/` | Get session + full message history |
| `DELETE` | `/api/chat/sessions/{id}/` | Permanently delete a session |
| `POST` | `/api/chat/sessions/{id}/messages/` | Send a message and receive an AI reply |
| `POST` | `/api/chat/sessions/{id}/archive/` | Archive a session |

#### Example: Send a message

```bash
curl -X POST http://localhost:8000/api/chat/sessions/{id}/messages/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is the capital of France?"}'
```

```json
{
  "success": true,
  "data": {
    "user_message": { "id": "...", "role": "user", "content": "What is the capital of France?", "created_at": "..." },
    "ai_message":   { "id": "...", "role": "assistant", "content": "The capital of France is Paris.", "created_at": "..." }
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created |
| `204` | No Content (delete) |
| `400` | Bad Request / Validation Error |
| `401` | Unauthorized |
| `403` | Forbidden |
| `404` | Not Found |
| `410` | Gone (archived/expired session) |
| `429` | Rate Limit Exceeded |
| `502` | AI Service Error |
| `504` | AI Service Timeout |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required)* | Django secret key |
| `DEBUG` | `True` | Enable debug mode |
| `AI_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `mock` |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Gemini API key |
| `AI_MODEL` | `claude-3-haiku-20240307` | Model identifier |
| `AI_MAX_TOKENS` | `1024` | Max tokens per AI response |
| `AI_TIMEOUT_SECONDS` | `30` | Timeout for AI requests |
| `AI_SYSTEM_PROMPT` | *(default prompt)* | System prompt injected into every session |
| `DB_*` | — | PostgreSQL connection settings (production) |

---

## Assumptions

1. **Single response per message** — the system sends one user message and expects one AI response. Streaming is not implemented but the provider abstraction supports it.
2. **Context window** — the last 20 messages are forwarded to the AI on each request (configurable via `CONTEXT_WINDOW` in `chat/services.py`).
3. **Session ownership** — sessions are strictly user-scoped; no cross-user access.
4. **Soft delete via archive** — archiving sets `status=archived` and blocks further messages; hard delete removes all data permanently.
5. **Auto-title** — if a session has no title (or is titled "New Conversation") and fewer than 2 messages exist, the title is set to the first 60 characters of the user's opening message.
6. **Graceful AI failure** — if an AI call fails, a human-readable error is saved as an assistant message and `502`/`504` is returned.
7. **Mock provider fallback** — if no API key is provided or a provider fails to initialise, the system falls back to `MockProvider` rather than crashing on startup.

---

## Design Decisions

**Provider abstraction** — `BaseAIProvider` makes it trivial to add new LLMs (Gemini, Mistral, local Ollama) without touching the service or view layers.

**Layered settings** — `base → development / production` avoids config duplication and keeps secrets out of source control.

**Structured JSON logging** — every request and AI call is emitted as a JSON object, making it straightforward to ingest into Datadog, CloudWatch, or any log aggregator.

**Custom exception hierarchy** — typed exceptions (`AIServiceException`, `AITimeoutException`, `SessionNotFoundException`) map cleanly to HTTP status codes and produce consistent error envelopes across the entire API.

**Rate limiting on the message endpoint** — protects both server resources and AI API quotas (default: 30 requests/minute per user, configurable).