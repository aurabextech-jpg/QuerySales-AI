<div align="center">

# 🤖 SalesOps Agent — Backend

**AI-Powered Autonomous Sales Operations Agent**

An intelligent backend that automates lead discovery, CRM management, and client outreach — bridging public business directories, ERPNext CRM, and Google Workspace through natural language.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Neon Postgres](https://img.shields.io/badge/Neon-Postgres-00E599?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## 📑 Table of Contents

- [About The Project](#about-the-project)
  - [Built With](#built-with)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Public Endpoints & OAuth Compliance](#public-endpoints--oauth-compliance)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

---

## About The Project

**SalesOps Agent** is a multi-agent AI system that acts as an autonomous sales operations assistant. It accepts natural language instructions and routes them to specialized sub-agents — each responsible for a distinct sales workflow — eliminating the manual, repetitive tasks that slow down sales teams.

The system intelligently coordinates between:

- **Public business directories** (Google Places) for real-time lead discovery
- **Your CRM** (ERPNext) for pipeline management and lead tracking
- **Google Workspace** (Gmail & Calendar) for personalized outreach and scheduling

All interactions happen through a conversational chat interface with full support for **English, Urdu, and Roman Urdu**.

### Built With

| Layer | Technology |
|-------|-----------|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.13+) |
| **Database** | [Neon Postgres](https://neon.tech/) (Serverless) via `SQLAlchemy` (Async) |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Authentication** | Neon Auth (Better Auth) with JWT/JWKS validation |
| **AI Orchestration** | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) with tiered Gemini models |
| **LLM Providers** | Gemini 2.5 Pro / Flash / Flash-Lite, OpenRouter (GLM-4.5) |
| **External APIs** | ERPNext REST API, Google Places, Gmail, Google Calendar |
| **Deployment** | [Vercel](https://vercel.com/) Serverless Functions (`@vercel/python`) |

---

## Key Features

### 🔍 Lead Generation & Enrichment
- Discovers businesses via Google Places API filtered by industry, location, and rating
- Enriches prospects with contact info, reviews, and business context for qualification

### 💼 CRM Integration (ERPNext)
- Pushes discovered leads directly into your ERPNext CRM pipeline
- Automatically manages lead status, opportunity scores, and activity tracking

### ✉️ Smart Outreach & Communication
- Drafts and sends personalized introductory emails through Gmail
- Natively understands and communicates in **English, Urdu, and Roman Urdu**

### 📅 Calendar Scheduling
- Reads Google Calendar to find conflict-free time slots
- Books meetings with prospects directly from chat commands

### 🧠 Intelligent Multi-Agent Orchestration
- Routes tasks to specialized sub-agents (Lead Gen, CRM, Outreach) based on user intent
- Maintains conversation context and handles trivial greetings efficiently without invoking heavy LLMs

### 🔒 Security-First Design
- JWT-based authentication with JWKS validation via Neon Auth
- Encrypted credential storage (Fernet) for OAuth refresh tokens
- Correlation-ID error tracking — never leaks internal details to clients

---

## Architecture

```mermaid
graph TB
    subgraph Client
        UI["Frontend (Next.js)"]
    end

    subgraph Backend["SalesOps Backend (FastAPI)"]
        API["API Layer"]
        AUTH["JWT Auth Middleware"]
        ORCH["Orchestrator Agent"]

        subgraph Agents["Specialized Sub-Agents"]
            LG["Lead Gen Agent"]
            CRM_A["CRM Agent"]
            OUT["Outreach Agent"]
        end

        subgraph Tools["MCP Tool Layer"]
            GP["Google Places"]
            ERP["ERPNext Client"]
            GM["Gmail Client"]
            GC["Calendar Client"]
        end
    end

    subgraph External["External Services"]
        PLACES["Google Places API"]
        ERPNEXT["ERPNext CRM"]
        GMAIL["Gmail API"]
        GCAL["Google Calendar API"]
        LLM["Gemini / OpenRouter"]
    end

    subgraph Data["Data Layer"]
        DB[("Neon Postgres")]
    end

    UI -->|SSE / REST| API
    API --> AUTH --> ORCH
    ORCH -->|Intent Routing| LG & CRM_A & OUT
    LG --> GP --> PLACES
    CRM_A --> ERP --> ERPNEXT
    OUT --> GM --> GMAIL
    OUT --> GC --> GCAL
    ORCH --> LLM
    API --> DB
```

---

## Project Structure

```text
salesops-agent-backend/
│
├── agent_core/              # AI orchestration engine
│   ├── orchestrator.py      #   Multi-agent router with intent detection
│   └── tracing.py           #   Workflow tracing and run logging
│
├── api/
│   └── endpoints/           # FastAPI route handlers
│       ├── chat.py          #   SSE chat streaming endpoint
│       ├── dashboard.py     #   Analytics and metrics API
│       ├── runs.py          #   Agent run history
│       ├── logs.py          #   Workflow trace logs
│       ├── calendar.py      #   Calendar availability API
│       └── pages.py         #   Landing, Privacy Policy, ToS pages
│
├── core/                    # Application configuration
│   ├── config.py            #   Pydantic Settings (env var management)
│   └── security.py          #   JWT validation, token encryption
│
├── db/                      # Data access layer
│   ├── models.py            #   SQLAlchemy ORM models
│   └── session.py           #   Async database session factory
│
├── mcp_tools/               # External service integrations (MCP tools)
│   ├── erpnext.py           #   ERPNext CRM operations
│   ├── gmail.py             #   Email sending via Gmail
│   ├── google_calendar.py   #   Calendar read/write operations
│   └── google_places.py     #   Business discovery & enrichment
│
├── alembic/                 # Database migration scripts
├── scripts/
│   └── get_google_token.py  # OAuth token helper utility
├── tests/                   # Automated test suites
│
├── main.py                  # FastAPI application entry point
├── pyproject.toml           # Project metadata and dependencies
├── requirements.txt         # Pip-compatible dependency list
├── vercel.json              # Vercel deployment configuration
├── .env.example             # Environment variable template
└── .gitignore
```

---

## Getting Started

Follow these steps to get a local development copy up and running.

### Prerequisites

Ensure the following are installed on your system:

- **Python 3.13+**
  ```sh
  python --version
  ```
- **pip** (or [uv](https://docs.astral.sh/uv/) for faster installs)
  ```sh
  pip --version
  ```
- **PostgreSQL client** (for Alembic migrations)
- A **Neon Postgres** database ([create one free](https://neon.tech/))
- API keys for: **Google Places**, **Gmail App Password**, **Gemini**, and an **ERPNext** instance

### Installation

1. **Clone the repository**
   ```sh
   git clone https://github.com/Sheikh-Muhammad-Mujtaba/AISeekho-challenge.git
   cd AISeekho-challenge/salesops-agent-backend
   ```

2. **Create and activate a virtual environment**
   ```sh
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```sh
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

5. **Run database migrations**
   ```sh
   alembic upgrade head
   ```

6. **Start the development server**
   ```sh
   uvicorn main:app --reload
   ```

7. **Verify** — Open your browser and navigate to:
   - API Root: `http://localhost:8000/health`
   - Interactive Docs: `http://localhost:8000/docs`

### Environment Variables

Create a `.env` file from the provided template. All variables are **required** unless noted otherwise.

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Neon Postgres connection string (asyncpg driver) | `postgresql+asyncpg://user:pass@host/db` |
| `ERPNEXT_BASE_URL` | ERPNext instance URL | `https://erp.example.com` |
| `ERPNEXT_API_TOKEN` | ERPNext API key:secret pair | `api_key:api_secret` |
| `GOOGLE_PLACES_API_KEY` | Google Places API key | — |
| `GOOGLE_CALENDAR_CLIENT_ID` | Google OAuth Client ID | — |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | Google OAuth Client Secret | — |
| `GOOGLE_CALENDAR_REFRESH_TOKEN` | Initial refresh token (stored encrypted in DB after first use) | — |
| `GMAIL_USER` | Gmail address for outbound emails | `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not account password) | — |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `GEMINI_BASE_URL` | Gemini OpenAI-compatible endpoint | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `GEMINI_MODEL` | Default Gemini model | `gemini-2.5-flash` |
| `OPENROUTER_API_KEY` | OpenRouter API key (for CRM agent) | — |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored tokens | Generate via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `NEON_AUTH_URL` | Neon Auth base URL | `https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth` |
| `NEON_AUTH_JWKS_URL` | Neon Auth JWKS endpoint for JWT validation | `https://ep-xxx.neonauth.region.aws.neon.tech/neondb/auth/.well-known/jwks.json` |
| `GOOGLE_SITE_VERIFICATION` | Google Search Console verification code | — |

> [!IMPORTANT]
> Never commit your `.env` file. The `.gitignore` already excludes it.

---

## API Reference

All API endpoints are prefixed under their respective groups. Full interactive documentation is available at `/docs` (Swagger UI) when the server is running.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/health` | Health check | ❌ |
| `GET` | `/` | Landing page | ❌ |
| `GET` | `/privacy` | Privacy Policy page | ❌ |
| `GET` | `/terms` | Terms of Service page | ❌ |
| `POST` | `/api/chat/` | Send a message to the AI agent (SSE stream) | ✅ |
| `GET` | `/api/runs/` | List agent run history | ✅ |
| `GET` | `/api/workflows/{run_id}` | Get workflow trace logs for a run | ✅ |
| `GET` | `/api/dashboard/` | Dashboard analytics and metrics | ✅ |
| `GET` | `/api/calendar/` | Calendar availability | ✅ |

> [!NOTE]
> Endpoints marked with ✅ require a valid JWT Bearer token issued by Neon Auth.

---

## Testing

The project includes unit, integration, and end-to-end tests:

```sh
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_e2e.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## Deployment

The backend is configured for serverless deployment on **Vercel** using the `@vercel/python` runtime.

1. **Link your repository** to a Vercel project
2. **Set environment variables** in Vercel Dashboard → Settings → Environment Variables
3. **Deploy** — Vercel automatically builds and deploys on every push to `main`

The `vercel.json` configuration routes all traffic through the FastAPI entry point (`main.py`) with a max Lambda size of **50 MB**.

> [!TIP]
> For local testing of the Vercel build, install the [Vercel CLI](https://vercel.com/docs/cli) and run `vercel dev`.

---

## Public Endpoints & OAuth Compliance

To comply with **Google OAuth consent screen** requirements, the backend serves these public pages:

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Responsive landing page describing the application |
| `GET /privacy` | Privacy Policy |
| `GET /terms` | Terms of Service |
| `GET /google{code}.html` | Google Search Console domain verification |

---

## Roadmap

- [x] Multi-agent orchestration with intent routing
- [x] Lead discovery via Google Places API
- [x] ERPNext CRM integration (create/update leads)
- [x] Gmail-based outreach with personalized templates
- [x] Google Calendar scheduling
- [x] JWT authentication via Neon Auth
- [x] Workflow tracing and run logging
- [x] Vercel serverless deployment
- [ ] Webhook-based real-time CRM sync
- [ ] Advanced lead scoring with ML
- [ ] Multi-tenant support
- [ ] Rate limiting and API throttling
- [ ] Observability dashboards (OpenTelemetry)

See the [open issues](https://github.com/Sheikh-Muhammad-Mujtaba/AISeekho-challenge/issues) for a full list of proposed features and known issues.

---

## Contributing

Contributions make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feat/amazing-feature`)
3. Commit your Changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the Branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

> [!NOTE]
> Please follow [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages.

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

## Contact

**Muhammad Mujtaba** — [@Sheikh-Muhammad-Mujtaba](https://github.com/Sheikh-Muhammad-Mujtaba)

Project Link: [https://github.com/Sheikh-Muhammad-Mujtaba/AISeekho-challenge](https://github.com/Sheikh-Muhammad-Mujtaba/AISeekho-challenge)

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — Modern, high-performance web framework
- [Neon](https://neon.tech/) — Serverless Postgres with branching
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — Multi-agent orchestration framework
- [Google Gemini](https://ai.google.dev/) — Large language model powering the agents
- [ERPNext](https://erpnext.com/) — Open source ERP and CRM
- [Vercel](https://vercel.com/) — Serverless deployment platform
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — README structure inspiration
- [Shields.io](https://shields.io/) — Badges for open source projects

---

<div align="center">

**[⬆ Back to Top](#-salesops-agent--backend)**

</div>
