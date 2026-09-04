# QuerySales AI — Final Development Handover Specification

## 1. ROLE

You are the lead software engineer responsible for completing this project.

You have an existing repository containing:

* Python/FastAPI backend
* AI Agent Orchestrator
* MCP/tool-calling infrastructure
* PostgreSQL + SQLAlchemy + Alembic
* Authentication
* Agent run logging/tracing
* ERPNext integration
* Gmail integration
* Existing React Native application

The existing React Native application is NOT the final frontend.

Due to the extremely limited development time, **do NOT build or continue the mobile application**.

Instead, create a **standalone Next.js web dashboard** that consumes the existing backend APIs and reuses as much existing backend functionality as possible.

The goal is to produce a working, polished, demonstrable MVP — not a production-scale SaaS platform.

---

# 2. PRODUCT

Product name:

**QuerySales AI**

Positioning:

> An autonomous AI sales employee that understands company knowledge, analyzes leads, reasons about opportunities, plans sales actions, and executes CRM/outreach actions using tools.

The system should demonstrate:

**Knowledge → RAG → Agent Reasoning → Planning → Tool Calling → Sales Action → Trace/Logs**

This workflow is the core of the hackathon demo.

---

# 3. VERY IMPORTANT DEVELOPMENT RULES

Follow these rules throughout development:

### Rule 1 — Reuse existing backend

Do NOT rewrite the existing FastAPI backend from scratch.

First inspect the repository and identify:

* existing API endpoints
* authentication
* database models
* agent orchestrator
* tool calling
* MCP tools
* tracing
* Gmail integration
* ERPNext integration
* existing lead functionality

Reuse these wherever possible.

---

### Rule 2 — React Native is reference only

The existing React Native app contains useful UI/UX ideas and components.

Use it as a reference for:

* dashboard information architecture
* workflow timeline
* agent logs
* cards
* CRM/lead screens
* existing terminology
* existing API usage

But DO NOT spend time maintaining or improving the React Native application.

The new frontend must be:

**Next.js + TypeScript + Tailwind CSS**

---

### Rule 3 — Do not overengineer

We have approximately 12 hours.

Do NOT build:

* complex multi-agent architecture
* WhatsApp integration
* voice/calling system
* LinkedIn automation
* Google Places
* Google Calendar
* advanced scraping
* enterprise RBAC
* complex billing
* complex notification systems
* production-grade multi-tenancy
* unnecessary microservices
* Kubernetes
* complicated event-driven architecture

The objective is a strong working demo.

---

# 4. FINAL ARCHITECTURE

Use this architecture:

```text
                    ┌───────────────────────┐
                    │      Next.js Web      │
                    │       Dashboard      │
                    └───────────┬───────────┘
                                │ REST API
                                ▼
                    ┌───────────────────────┐
                    │     FastAPI Backend   │
                    ├───────────────────────┤
                    │ Authentication        │
                    │ Agent API             │
                    │ Knowledge API          │
                    │ Lead API               │
                    │ Run/Trace API          │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
       ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
       │ AI Agent    │  │ RAG Engine   │  │ MCP Tools    │
       │ Orchestrator│  │              │  │              │
       └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
              │                │                  │
              └────────────────┼──────────────────┘
                               ▼
                    ┌───────────────────────┐
                    │ Neon PostgreSQL       │
                    │                       │
                    │ Normal relational DB  │
                    │ + pgvector            │
                    └───────────────────────┘
```

---

# 5. DATABASE

Use:

**Neon PostgreSQL**

Enable:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Use SQLAlchemy/Alembic as already used by the backend.

Do NOT introduce another database.

---

# 6. DATABASE DATA MODEL

Create only the minimum required models.

## users

Reuse the existing user model if it already exists.

Required functionality:

* login
* logout
* authenticated dashboard

Do not build complicated RBAC.

---

## leads

If an existing lead model exists, reuse/adapt it.

Minimum fields:

```text
id
name
company
email
industry
website
status
score
pain_points
notes
created_at
updated_at
```

Example statuses:

```text
New
Analyzing
Qualified
Nurture
Disqualified
Contacted
```

---

## knowledge_documents

```text
id
filename
title
file_type
content
status
created_at
updated_at
```

---

## knowledge_chunks

```text
id
document_id
content
chunk_index
embedding
metadata
created_at
```

The `embedding` column must use PostgreSQL pgvector.

---

## agent_runs

Reuse existing run/log model if available.

The system should record:

```text
run_id
user_id
lead_id
status
started_at
completed_at
final_result
```

---

## agent_events

Reuse the existing tracing/logging architecture if possible.

Each run should be able to display events such as:

```text
OBSERVE
RETRIEVE
REASON
PLAN
TOOL_CALL
RESULT
COMPLETE
```

---

# 7. AI MODEL CONFIGURATION

This is important.

The system should NOT hard-code OpenAI.

Create a configuration system allowing an administrator/user to configure an **OpenAI-compatible LLM provider**.

Configuration fields:

```text
Provider Name
Base URL
API Key
Model Name
Temperature
Max Tokens
```

Examples of compatible providers:

```text
OpenAI
OpenRouter
Alibaba/Qwen compatible endpoint
Other OpenAI-compatible providers
```

The backend should use:

```text
base_url
api_key
model
```

rather than hard-coding a provider.

The frontend should provide a Settings page where these values can be configured.

API keys must never be exposed in frontend logs or agent traces.

---

# 8. EMBEDDING MODEL CONFIGURATION

Implement the same concept for embeddings.

The embedding provider should be configurable rather than hard-coded.

Configuration:

```text
Embedding Provider
Embedding Base URL
Embedding API Key
Embedding Model
Embedding Dimension
```

The system should support an **OpenAI-compatible embeddings endpoint**.

The RAG pipeline should use whichever embedding configuration is currently active.

Important:

The embedding dimension stored in pgvector must match the configured embedding model.

Do not silently change dimensions.

If the database schema requires a fixed dimension, document it clearly and configure the MVP around one selected embedding model.

---

# 9. KNOWLEDGE BASE

Create a Knowledge Base page.

The user should be able to:

1. Upload a document
2. See uploaded documents
3. Process/index the document
4. See processing status
5. Delete a document

For the MVP support:

```text
PDF
TXT
MD
```

If PDF extraction becomes a time risk, prioritize TXT/MD first and make PDF support secondary.

---

# 10. RAG PIPELINE

Implement the complete pipeline:

```text
Upload File
      ↓
Extract Text
      ↓
Clean Text
      ↓
Chunk Text
      ↓
Generate Embeddings
      ↓
Store chunks + embeddings
      ↓
pgvector
```

When the agent needs knowledge:

```text
User/Agent Query
      ↓
Generate Query Embedding
      ↓
pgvector similarity search
      ↓
Top K relevant chunks
      ↓
Return context to Agent
```

Default:

```text
top_k = 5
```

The search function should return:

```text
document
chunk
similarity score
metadata
```

---

# 11. KNOWLEDGE SEARCH MUST BE AN AGENT TOOL

This is extremely important.

Do NOT simply perform RAG before calling the LLM.

Create an actual agent tool:

```text
search_knowledge(query)
```

The agent should decide when it needs company knowledge.

Example:

```text
Agent:
I need information about solutions relevant to this manufacturing lead.

Tool:
search_knowledge(
    "manufacturing inventory management solutions"
)

Tool Result:
Relevant company case study...
Relevant product documentation...
```

This demonstrates actual autonomous tool usage.

---

# 12. AGENT WORKFLOW

The agent should follow this conceptual loop:

```text
OBSERVE
   ↓
Understand Lead
   ↓
RETRIEVE
   ↓
Search Knowledge Base
   ↓
REASON
   ↓
Evaluate Lead Fit
   ↓
PLAN
   ↓
Determine Sales Action
   ↓
ACT
   ↓
Call appropriate tool
   ↓
RESULT
   ↓
Update Lead / Create Outreach / Log Result
```

The agent should NOT merely return a JSON response from one LLM call.

It must actually use tools.

---

# 13. AGENT TOOLS

Prioritize these tools:

### Tool 1 — Knowledge Search

```text
search_knowledge(query)
```

### Tool 2 — Get Lead

```text
get_lead(lead_id)
```

### Tool 3 — Update Lead

```text
update_lead(lead_id, ...)
```

### Tool 4 — Create Opportunity / Follow-up

Reuse existing ERPNext tool if stable.

### Tool 5 — Draft Outreach

Generate personalized outreach based on:

* lead information
* company knowledge
* agent reasoning

### Tool 6 — Gmail

Reuse the existing Gmail integration.

For the MVP:

**Prefer drafting email first and require human approval before sending.**

If the existing Gmail integration is already stable, support:

```text
Create Draft
```

and optionally:

```text
Send Email
```

Do not risk the entire demo on email sending.

---

# 14. AGENT OUTPUT

The final agent result should contain structured information:

```json
{
  "lead_score": 93,
  "qualification": "Qualified",
  "reasoning": "...",
  "pain_points": [],
  "matched_knowledge": [],
  "recommended_action": "...",
  "outreach": {
    "subject": "...",
    "body": "..."
  }
}
```

Do not expose hidden chain-of-thought.

The UI should show concise business reasoning/summaries rather than private internal reasoning.

---

# 15. NEXT.JS APPLICATION

Create a new application:

```text
querysales-web/
```

Use:

```text
Next.js
TypeScript
Tailwind CSS
```

Use a clean modern SaaS dashboard design.

Do not waste time building a complicated design system.

---

# 16. REQUIRED ROUTES

Create these routes.

## /login

Simple login page.

Fields:

```text
Email
Password
```

Actions:

```text
Login
```

After successful authentication:

```text
/dashboard
```

---

# 17. /dashboard

This is the main screen.

Show:

### KPI Cards

```text
Total Leads
Qualified Leads
Outreach Sent
Active Agent Runs
Knowledge Documents
```

### Lead Overview

Display recent leads.

Columns:

```text
Company
Industry
Lead Score
Status
Last Activity
```

### Agent Activity

Show recent agent runs.

Example:

```text
Acme Manufacturing
Qualified — 93
2 minutes ago
```

### Recent Actions

Show:

```text
Knowledge Retrieved
Lead Updated
Email Drafted
Opportunity Created
```

---

# 18. /leads

Lead management page.

Show:

* lead list
* search
* filters
* lead score
* status
* company
* industry

Clicking a lead opens a detail view.

Lead detail should contain:

```text
Company
Contact
Industry
Website
Pain Points
Score
Status
Notes
Agent Actions
```

Primary CTA:

```text
Analyze with QuerySales AI
```

---

# 19. LEAD ANALYSIS EXPERIENCE

When user clicks:

**Analyze with QuerySales AI**

start an agent run.

The UI should show a live/progressive timeline.

Example:

```text
✓ Lead loaded

✓ Understanding lead requirements

✓ Searching company knowledge

✓ Retrieved 4 relevant documents

✓ Evaluating product fit

✓ Creating sales action plan

✓ Updating lead

✓ Drafting personalized outreach

✓ Analysis complete
```

This is one of the most important demo screens.

---

# 20. /runs/[id]

Create an Agent Run detail page.

Show:

### Header

```text
Agent Run
Acme Manufacturing
Qualified
93/100
```

### Timeline

```text
Observe
   ↓
Retrieve
   ↓
Tool Call
   ↓
Reason
   ↓
Plan
   ↓
Action
   ↓
Result
```

Each event should be expandable.

Example:

```text
SEARCH_KNOWLEDGE

Query:
"inventory management manufacturing"

Results:
4 matching knowledge chunks

Source:
Manufacturing Solutions.pdf
```

For tool calls:

```text
TOOL CALL

update_lead

Status:
Qualified

Score:
93
```

For outreach:

```text
OUTREACH DRAFT

Subject:
Improve inventory visibility at Acme Manufacturing

[Email Body]

[Approve & Send]
```

---

# 21. /knowledge

Knowledge Base UI.

Show:

```text
Knowledge Documents
```

Table:

```text
Document
Type
Chunks
Status
Created
Actions
```

Upload button:

```text
Upload Knowledge
```

After upload:

```text
Extracting
Chunking
Embedding
Indexed
```

---

# 22. /settings

Create configuration sections.

## LLM Configuration

Fields:

```text
Provider
Base URL
API Key
Model
Temperature
Max Tokens
```

Button:

```text
Test Connection
Save Configuration
```

---

## Embedding Configuration

Fields:

```text
Provider
Base URL
API Key
Model
Dimension
```

Buttons:

```text
Test Connection
Save Configuration
```

---

## Database

Display:

```text
PostgreSQL
Connected
pgvector
Enabled
```

Do not expose the actual database password.

---

# 23. SIDEBAR

Create a clean sidebar:

```text
QuerySales AI

Dashboard
Leads
Knowledge
Agent Runs
Settings

----------------

User
Logout
```

Keep navigation simple.

---

# 24. DESIGN DIRECTION

Use the existing React Native application for UI/UX inspiration.

Inspect these existing components/screens if present:

```text
AuroraGradient.tsx
GlassCard.tsx
WorkflowTimeline.tsx
OutcomeDashboardScreen.tsx
TraceLogsScreen.tsx
RunLogCard.tsx
CRMLeadsScreen.tsx
SimulationConsoleScreen.tsx
```

Extract the useful concepts and recreate them appropriately in Next.js.

Do not blindly copy React Native code.

The final web dashboard should look like a polished AI SaaS application.

Prioritize:

* clean typography
* cards
* good spacing
* status badges
* timeline
* tables
* responsive layout
* clear CTAs
* loading states
* error states

---

# 25. DEMO DATA

Create seed/demo data.

The application must NOT open as an empty dashboard.

Seed:

### Company

```text
Demo Manufacturing Solutions
```

### Leads

Create approximately 5 demo leads.

Example:

```text
Acme Manufacturing
Industry: Manufacturing
Pain Point: Inventory visibility
Status: New
```

```text
PakTech Industries
Industry: Industrial
Pain Point: Manual sales operations
Status: New
```

```text
Karachi Components Ltd
Industry: Manufacturing
Pain Point: Supply chain inefficiency
Status: New
```

Include different scores/statuses so the dashboard looks realistic.

---

# 26. DEMO KNOWLEDGE

Create demo knowledge content.

Example documents:

```text
Manufacturing Solutions.pdf
Inventory Management Case Study.md
Company Products.md
Sales Playbook.md
```

The content should contain realistic information about:

* inventory management
* ERP integration
* manufacturing workflows
* sales automation
* business benefits
* customer case studies

The agent must actually retrieve this content through pgvector during the demo.

---

# 27. IDEAL DEMO FLOW

The complete demo should work like this:

### Step 1

Login.

### Step 2

Open Dashboard.

Show:

```text
5 Leads
2 Qualified
8 Agent Actions
4 Knowledge Documents
```

### Step 3

Open:

```text
Acme Manufacturing
```

### Step 4

Click:

```text
Analyze with QuerySales AI
```

### Step 5

Agent starts.

Timeline:

```text
Observe
↓
Retrieve Knowledge
↓
Reason
↓
Plan
↓
Tool Call
↓
Update Lead
↓
Draft Outreach
```

### Step 6

Agent retrieves:

```text
Manufacturing Solutions
Inventory Management Case Study
```

using actual vector search.

### Step 7

Agent determines:

```text
Lead Score: 93/100

Status: Qualified
```

### Step 8

Agent updates the lead using a tool.

### Step 9

Agent generates personalized outreach.

Example:

```text
Subject:
Improving inventory visibility at Acme Manufacturing
```

### Step 10

Show:

```text
Approve & Send
```

or:

```text
Create Gmail Draft
```

### Step 11

Dashboard updates:

```text
Qualified Leads +1
Agent Runs +1
Outreach Drafts +1
```

This is the complete hackathon demonstration.

---

# 28. API DESIGN

Expose clean backend APIs.

Minimum:

```text
POST /auth/login

GET /dashboard/stats

GET /leads
GET /leads/{id}
POST /leads/{id}/analyze
PATCH /leads/{id}

GET /knowledge
POST /knowledge/upload
POST /knowledge/{id}/process
DELETE /knowledge/{id}

POST /knowledge/search

GET /runs
GET /runs/{id}

GET /settings/llm
PUT /settings/llm

GET /settings/embedding
PUT /settings/embedding
```

Adapt these to the existing API conventions instead of blindly creating duplicates.

---

# 29. ENVIRONMENT VARIABLES

Create clear `.env.example` files.

Frontend:

```text
NEXT_PUBLIC_API_URL=
```

Backend:

```text
DATABASE_URL=

LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=

EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
```

If configuration is stored in PostgreSQL, environment variables should provide safe defaults/bootstrap configuration.

Never commit real API keys.

---

# 30. SECURITY

For the MVP:

* never expose API keys to browser JavaScript
* keep provider API calls server-side
* validate uploaded files
* restrict upload size
* validate file types
* use authenticated API requests
* never display secrets in logs
* do not expose database credentials
* sanitize user-provided content where appropriate

Do not spend hours implementing enterprise security.

---

# 31. ERROR HANDLING

Every major UI operation needs:

```text
Loading
Success
Error
Empty
```

states.

Examples:

```text
Embedding failed
LLM connection failed
Knowledge indexing failed
Agent run failed
Invalid credentials
Backend unavailable
```

Show useful user-facing messages.

---

# 32. DEVELOPMENT PRIORITY

Work in this exact order.

## P0 — Must Work

1. Inspect existing repository.
2. Understand existing backend.
3. Set up Neon PostgreSQL.
4. Enable pgvector.
5. Add knowledge models.
6. Implement document ingestion.
7. Implement embeddings.
8. Implement vector search.
9. Create `search_knowledge` agent tool.
10. Connect RAG to orchestrator.
11. Verify tool calling.
12. Create/seed demo leads.
13. Create Next.js app.
14. Implement login.
15. Implement dashboard.
16. Implement leads.
17. Implement knowledge page.
18. Implement agent run timeline.
19. Implement settings.
20. Run complete end-to-end demo.

---

## P1 — Only If Time Remains

* PDF support improvements
* live streaming agent events
* Gmail draft integration
* better charts
* advanced filters
* search
* polished animations
* full-text PostgreSQL search

---

## P2 — Ignore For Now

Do NOT build:

* WhatsApp
* calling
* LinkedIn
* multi-agent swarm
* complex scraping
* billing
* teams
* advanced permissions
* mobile application
* complex analytics
* deployment automation unless required

---

# 33. IMPORTANT: POSTGRES FULL-TEXT SEARCH

PostgreSQL full-text search is optional.

Do NOT implement it before pgvector RAG works.

Priority:

```text
pgvector RAG
     >
Full-text search
```

If there is sufficient time, hybrid retrieval can later be implemented:

```text
Vector Search
+
PostgreSQL Full Text Search
```

But this is NOT required for the first working MVP.

---

# 34. IMPORTANT: AGENT ARCHITECTURE

Do NOT convert this into a complicated multi-agent system.

Use:

```text
One main autonomous sales agent
+
Multiple tools
+
RAG
+
Agent tracing
```

The agent should be capable of deciding:

```text
What information do I need?
        ↓
Which tool should I use?
        ↓
What does the result mean?
        ↓
What action should I take?
        ↓
Which tool should execute that action?
```

This is sufficient to demonstrate autonomous agent behavior.

---

# 35. EXISTING CODE REUSE

Before implementing anything, inspect the existing repository and make a reuse map.

Create a short internal document:

```text
EXISTING → REUSE
```

For example:

```text
Existing Orchestrator → REUSE
Existing Auth → REUSE
Existing DB → REUSE
Existing Tool Framework → REUSE
Existing Gmail Tool → REUSE
Existing Tracing → REUSE
Existing Lead Model → ADAPT
Existing React Native UI → REFERENCE
```

Do not duplicate functionality unnecessarily.

---

# 36. DEVELOPMENT PROCESS

Do NOT spend a long time explaining the plan back to me.

You are authorized to:

1. inspect the repository
2. identify reusable components
3. make the architecture decisions
4. implement the required changes
5. run migrations
6. run tests
7. fix errors
8. create demo data
9. connect frontend/backend
10. verify the complete workflow

Start implementation immediately after a short repository audit.

---

# 37. ACCEPTANCE CRITERIA

The project is considered complete when the following works:

```text
Login
  ↓
Dashboard
  ↓
Lead
  ↓
Analyze Lead
  ↓
Agent Starts
  ↓
Agent Calls search_knowledge
  ↓
pgvector Returns Relevant Knowledge
  ↓
Agent Qualifies Lead
  ↓
Agent Calls Lead Tool
  ↓
Lead Updated
  ↓
Agent Generates Personalized Outreach
  ↓
Run Timeline Shows Everything
  ↓
User Can Approve/Create Draft
```

The entire flow must work using actual backend functionality.

---

# 38. FINAL QUALITY CHECK

Before declaring the work complete, verify:

### Backend

* [ ] FastAPI starts
* [ ] PostgreSQL connects
* [ ] pgvector works
* [ ] migrations work
* [ ] knowledge upload works
* [ ] embeddings work
* [ ] vector search works
* [ ] agent can call search_knowledge
* [ ] agent can call lead tools
* [ ] agent runs are logged
* [ ] errors are handled

### Frontend

* [ ] Next.js starts
* [ ] Login works
* [ ] Dashboard loads
* [ ] Leads load
* [ ] Knowledge documents load
* [ ] Upload works
* [ ] Agent analysis works
* [ ] Run timeline works
* [ ] Settings work
* [ ] Responsive layout works
* [ ] No major console errors

### Demo

* [ ] Demo data exists
* [ ] Demo knowledge exists
* [ ] Lead analysis works
* [ ] RAG retrieval is real
* [ ] Tool calling is real
* [ ] Lead update is real
* [ ] Outreach generation is real
* [ ] Timeline visibly proves agentic workflow

---

# 39. FINAL INSTRUCTION

Do not optimize for code volume.

Optimize for:

**Working end-to-end functionality + visible autonomous behavior + RAG + tool calling + polished web UI.**

If you encounter a feature that cannot realistically be completed within the available time:

1. simplify it,
2. preserve the core workflow,
3. move it to P1/P2,
4. continue with the working MVP.

Never allow an optional feature to block the core demo.

The final product should feel like:

> **An AI Sales Employee with a real memory/knowledge base that can understand leads, retrieve company knowledge, make decisions, plan actions, use business tools, and show exactly what it did.**

Start by auditing the existing repository and then begin implementation.


# 40. MULTI-USER CONFIGURATION & DATA ISOLATION

This application must be designed around **user-owned configuration**.

Every authenticated user must have their own independent configuration.

Do NOT create a single global LLM, embedding, email, or integration configuration shared by all users.

The architecture must support:

```text
User A
 ├── LLM Configuration
 ├── Embedding Configuration
 ├── Email Configuration
 └── Integration Configuration

User B
 ├── LLM Configuration
 ├── Embedding Configuration
 ├── Email Configuration
 └── Integration Configuration
```

Each user's configuration belongs exclusively to that authenticated user.

---

# 41. USER CONFIGURATION MODEL

Create a user-scoped configuration system.

Every configuration record must contain an ownership relationship such as:

```text
user_id
```

Example conceptual structure:

```text
users
   │
   ├── user_llm_config
   ├── user_embedding_config
   ├── user_email_config
   └── user_integration_config
```

Alternatively, these can be consolidated into appropriate configuration tables, but **every sensitive configuration must be associated with the authenticated user's ID**.

Never retrieve configuration without applying the authenticated user's ownership filter.

---

# 42. LLM CONFIGURATION — PER USER

Each user can configure their own OpenAI-compatible LLM provider.

Example fields:

```text
user_id
provider_name
base_url
api_key_encrypted
model
temperature
max_tokens
created_at
updated_at
```

Examples:

```text
OpenAI
OpenRouter
Qwen-compatible endpoint
Alibaba-compatible endpoint
Other OpenAI-compatible providers
```

The user configures these values from:

```text
Dashboard → Settings → AI / LLM
```

The configuration is stored against that user.

When the agent runs, it must load the LLM configuration belonging to the currently authenticated user.

Example:

```text
Authenticated User
        ↓
user_id
        ↓
Load User's LLM Configuration
        ↓
Decrypt API Key server-side
        ↓
Initialize LLM Client
        ↓
Run Agent
```

Never use another user's configuration.

---

# 43. EMBEDDING CONFIGURATION — PER USER

Embedding configuration must also be user-specific.

Example:

```text
user_id
provider_name
base_url
api_key_encrypted
model
dimension
created_at
updated_at
```

Configuration UI:

```text
Dashboard
 → Settings
 → Embeddings
```

The user should be able to configure an OpenAI-compatible embedding provider.

The RAG pipeline must use the embedding configuration belonging to the authenticated user.

Example:

```text
User A
    ↓
User A Embedding Config
    ↓
Generate User A embedding
    ↓
User A knowledge base
```

Do not accidentally use a global embedding API key.

---

# 44. EMAIL CONFIGURATION — PER USER

Email configuration must also be user-specific.

The user should be able to configure their own email/outreach provider through:

```text
Dashboard
 → Settings
 → Email / Outreach
```

Support the existing Gmail integration if already implemented.

If the existing architecture supports OAuth tokens, store the required OAuth credentials/tokens securely and associate them with the authenticated user.

Conceptually:

```text
user_id
provider
email_address
access_token_encrypted
refresh_token_encrypted
token_expiry
created_at
updated_at
```

The agent must send/draft outreach using the currently authenticated user's email configuration.

Example:

```text
User A runs agent
        ↓
Agent loads User A email configuration
        ↓
Creates User A's email draft
```

User B must never be able to access User A's email credentials or drafts unless explicitly authorized through a future sharing system.

---

# 45. ENCRYPTION OF SENSITIVE CONFIGURATION

Sensitive credentials must NOT be stored as plaintext in PostgreSQL.

At minimum, encrypt:

```text
LLM API keys
Embedding API keys
Gmail access tokens
Gmail refresh tokens
Other integration secrets
```

Use strong authenticated encryption.

Preferred approach:

```text
AES-256-GCM
```

Do NOT implement custom cryptography.

Use a well-tested cryptographic library provided by the backend language/framework.

The encryption key itself must NOT be stored in PostgreSQL.

It must come from a secure server-side environment variable or secret-management mechanism.

Example:

```text
ENCRYPTION_KEY
```

The database stores:

```text
encrypted_value
```

not:

```text
plain_api_key
```

---

# 46. ENCRYPTION ARCHITECTURE

Use this flow:

```text
User enters API key
        ↓
HTTPS
        ↓
FastAPI backend
        ↓
Encrypt secret using AES-256-GCM
        ↓
PostgreSQL
        ↓
Encrypted value
```

When the agent needs the credential:

```text
PostgreSQL
    ↓
Encrypted value
    ↓
FastAPI backend
    ↓
Decrypt server-side
    ↓
Use credential
    ↓
Never return plaintext to frontend
```

The browser should NEVER receive decrypted API keys after they have been stored.

---

# 47. SECRET DISPLAY BEHAVIOR

When the user opens Settings, do NOT return the actual stored API key/token.

Instead show something like:

```text
API Key
••••••••••••••••••••••••
```

or:

```text
sk-••••••••••••••••
```

The frontend should only know:

```text
configured = true
```

not the actual secret.

Provide:

```text
Update API Key
Remove Configuration
Test Connection
```

rather than exposing the existing secret.

---

# 48. DATABASE SECURITY / USER ISOLATION

Every API endpoint that accesses user-owned data must derive the user identity from the authenticated session/token.

Do NOT trust:

```text
user_id
```

sent by the frontend for authorization.

For example, do NOT implement:

```text
GET /settings/llm?user_id=123
```

and trust that value.

Instead:

```text
Authenticated Request
        ↓
Backend extracts authenticated user_id
        ↓
Query configuration WHERE user_id = authenticated_user_id
```

This prevents users from changing a URL/request parameter and accessing another user's data.

---

# 49. USER DATA ISOLATION

The same principle applies to:

* leads
* knowledge documents
* knowledge chunks
* agent runs
* agent logs
* outreach history
* email drafts
* settings
* integrations

Every user-owned record must be scoped to the authenticated user.

Conceptually:

```text
User A
 ├── Leads A
 ├── Knowledge A
 ├── Agent Runs A
 ├── Outreach A
 └── Settings A

User B
 ├── Leads B
 ├── Knowledge B
 ├── Agent Runs B
 ├── Outreach B
 └── Settings B
```

User A must not be able to retrieve User B's records through manipulated API requests.

---

# 50. KNOWLEDGE BASE IS ALSO USER-SCOPED

This is particularly important for RAG.

Knowledge documents must belong to a user.

Example:

```text
knowledge_documents
-------------------
id
user_id
filename
title
...
```

And:

```text
knowledge_chunks
----------------
id
document_id
user_id
content
embedding
metadata
...
```

Vector search MUST be filtered by authenticated user.

Do NOT perform:

```text
similarity search across every user's knowledge
```

Instead:

```text
User ID
   +
Query Embedding
   ↓
pgvector similarity search
   ↓
WHERE user_id = authenticated_user_id
```

This prevents cross-user knowledge leakage.

---

# 51. AGENT RUNS ARE USER-SCOPED

Every agent run must belong to the authenticated user.

Example:

```text
agent_runs
----------
id
user_id
lead_id
status
started_at
completed_at
final_result
```

Agent logs/events must also be associated with the correct run/user.

The frontend should only display:

```text
Current User's Runs
```

---

# 52. AGENT CONFIGURATION RESOLUTION

When an agent starts, configuration resolution should follow:

```text
Authenticated User
        ↓
Load User Configuration
        ↓
LLM Configuration
        ↓
Embedding Configuration
        ↓
Email Configuration
        ↓
Initialize required clients
        ↓
Start Agent
```

Do not initialize one global LLM client using one global API key for all users.

Configuration should be resolved at request/agent-run level or through a safely scoped configuration service.

---

# 53. SETTINGS UI

The Settings page should contain:

```text
Settings

├── AI / LLM
│   ├── Provider
│   ├── Base URL
│   ├── API Key
│   ├── Model
│   ├── Temperature
│   ├── Max Tokens
│   ├── Test Connection
│   └── Save
│
├── Embeddings
│   ├── Provider
│   ├── Base URL
│   ├── API Key
│   ├── Model
│   ├── Dimension
│   ├── Test Connection
│   └── Save
│
├── Email / Outreach
│   ├── Provider
│   ├── Account
│   ├── Connect / Configure
│   ├── Test Connection
│   └── Remove
│
└── Database
    ├── Connection Status
    └── pgvector Status
```

Make the Settings UI easy to understand.

Show configuration status instead of exposing secrets:

```text
LLM
✓ Configured

Embeddings
✓ Configured

Email
✓ Connected
```

---

# 54. DEFAULT / FALLBACK CONFIGURATION

Do not automatically share an administrator's credentials with all users.

For the MVP, either:

### Option A — Recommended

Every user configures their own credentials.

OR:

### Option B

Allow a clearly defined system-level fallback configuration, but only if explicitly enabled.

If a fallback exists, make the resolution order explicit:

```text
User Configuration
       ↓
if missing
       ↓
Optional System Fallback
```

Never silently use another user's configuration.

---

# 55. CONFIGURATION TESTING

Each integration should provide a backend test endpoint.

Example:

```text
POST /settings/llm/test
POST /settings/embedding/test
POST /settings/email/test
```

The backend should:

1. authenticate the user
2. load that user's encrypted configuration
3. decrypt server-side
4. test the provider
5. return only success/failure information

Example:

```json
{
  "success": true,
  "message": "Connection successful"
}
```

Never return the API key/token.

---

# 56. LOGGING RULES FOR SECRETS

Absolutely do NOT log:

```text
API keys
OAuth access tokens
OAuth refresh tokens
Authorization headers
Database passwords
Encryption keys
```

Agent traces should show:

```text
LLM Provider: OpenAI-compatible
Model: configured-model
Status: success
```

but never:

```text
API Key: sk-xxxxx
```

---

# 57. MVP SECURITY PRIORITY

Because this is a hackathon MVP, prioritize security in this order:

```text
1. User authentication
2. User data isolation
3. Server-side secret handling
4. AES-256-GCM encryption
5. No secrets in logs
6. Knowledge/RAG user isolation
7. Secure API validation
```

Do not spend time implementing a complicated enterprise IAM platform.

Simple authenticated user accounts with proper ownership checks are sufficient for the MVP.

---

# 58. MULTI-USER ACCEPTANCE TEST

Before completion, create at least two test users:

```text
User A
User B
```

Verify:

### User A

Can see:

```text
User A Leads
User A Knowledge
User A Agent Runs
User A Settings
```

### User B

Can see:

```text
User B Leads
User B Knowledge
User B Agent Runs
User B Settings
```

Verify that:

```text
User A cannot access User B data.
User B cannot access User A data.
```

Also verify that:

```text
User A's LLM API key
User A's embedding API key
User A's email credentials
```

cannot be retrieved through the frontend or another user's API request.

---

# 59. FINAL ARCHITECTURE WITH USER ISOLATION

The final architecture should conceptually be:

```text
                    ┌──────────────────────┐
                    │     Next.js Web      │
                    │      Dashboard       │
                    └──────────┬───────────┘
                               │
                         Authenticated
                            Request
                               │
                               ▼
                    ┌──────────────────────┐
                    │      FastAPI         │
                    │                      │
                    │ Auth / User Context  │
                    └──────────┬───────────┘
                               │
                     authenticated user_id
                               │
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
      ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
      │ User Config │   │ User RAG    │   │ User Agent   │
      │             │   │             │   │              │
      │ LLM         │   │ Documents   │   │ Runs         │
      │ Embeddings  │   │ Chunks      │   │ Tools        │
      │ Email       │   │ Vectors     │   │ Outreach     │
      └──────┬──────┘   └──────┬──────┘   └──────┬───────┘
             │                 │                  │
             └─────────────────┼──────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Neon PostgreSQL      │
                    │ + pgvector           │
                    │                      │
                    │ User-scoped data     │
                    │ Encrypted secrets    │
                    └──────────────────────┘
```

The key architectural principle is:

> **Every request, configuration, knowledge document, vector search, lead, agent run, and integration must be scoped to the authenticated user.**

The system must never treat external API credentials as global application credentials unless explicitly configured as a system fallback.

---

# 60. UPDATED DEFINITION OF DONE

The project is complete when:

* [ ] Multiple users can log in
* [ ] Each user has isolated data
* [ ] Each user has independent LLM configuration
* [ ] Each user has independent embedding configuration
* [ ] Each user has independent email configuration
* [ ] Sensitive credentials are encrypted at rest
* [ ] AES-256-GCM or an equally strong authenticated encryption mechanism is used
* [ ] Encryption key is stored outside the database
* [ ] Secrets never appear in frontend responses
* [ ] Secrets never appear in logs
* [ ] RAG is user-scoped
* [ ] pgvector search is user-scoped
* [ ] Agent runs are user-scoped
* [ ] Leads are user-scoped
* [ ] Settings are user-scoped
* [ ] User A cannot access User B's data
* [ ] User A cannot use User B's credentials
* [ ] Agent dynamically loads the authenticated user's configuration
* [ ] End-to-end demo works
