<p align="center">
  <h1 align="center">📱 SalesOps Agent — Mobile App</h1>
  <p align="center">
    An AI-powered sales operations companion built with React Native, featuring real-time agent chat, CRM management, lead discovery, and Google Calendar integration.
    <br />
    <br />
    <a href="#-getting-started"><strong>Get Started »</strong></a>
    ·
    <a href="#-architecture"><strong>Architecture »</strong></a>
    ·
    <a href="#-features"><strong>Features »</strong></a>
  </p>
</p>

---

## 📋 Table of Contents

- [About the Project](#-about-the-project)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Running the App](#running-the-app)
- [Project Structure](#-project-structure)
- [Screens](#-screens)
- [State Management](#-state-management)
- [API Services](#-api-services)
- [Design System](#-design-system)
- [Backend Integration](#-backend-integration)
- [Security](#-security)
- [Known Limitations](#-known-limitations)

---

## 🧐 About the Project

**SalesOps Agent** is the React Native mobile companion for the [SalesOps Agent Backend](../salesops-agent-backend/). It provides a conversational AI interface where sales teams can interact with an intelligent multi-agent system that automates lead generation, CRM operations, email outreach, meeting scheduling, and business discovery — all from a single chat interface.

The app communicates with a FastAPI backend powered by a Google ADK multi-agent orchestrator. The backend delegates user requests to specialized sub-agents (Lead Gen, CRM, Outreach) that interact with live APIs including ERPNext, Google Places, Google Calendar, and Gmail.

---

## ✨ Features

| Feature | Description |
|---|---|
| **AI Agent Chat** | Real-time conversational interface with streaming responses, token-by-token replay, and agent/tool step visibility |
| **Home Dashboard** | Metrics overview with quick-action chips, recent activity feed, and workflow playbook cards |
| **Lead Discovery** | Google Places–powered business search with one-tap CRM lead creation |
| **CRM Leads View** | Browse, search, and manage ERPNext leads directly from the app |
| **Outcome Dashboard** | Per-run analytics showing agent steps, tool calls, and final outcomes |
| **Trace Logs** | Detailed execution traces for debugging agent workflows |
| **Simulation Console** | Test agent workflows in a sandboxed simulation mode |
| **Google Calendar Sync** | Connect your Google Calendar via native OAuth for meeting scheduling |
| **Notifications** | Alert center for workflow completions and system events |
| **Account & Settings** | Profile management, theme toggling (dark/light), and calendar connection status |
| **Dark & Light Mode** | Full Aurora Intelligence design system with both dark navy and clean white themes |

---

## 🛠 Tech Stack

| Category | Technology |
|---|---|
| **Framework** | [React Native](https://reactnative.dev/) 0.85.3 (New Architecture) |
| **Language** | TypeScript 5.8+ |
| **Navigation** | React Navigation 7 (Native Stack + Bottom Tabs) |
| **State Management** | Redux Toolkit 2.x + React-Redux 9.x |
| **HTTP Client** | Axios with interceptor-based JWT auth |
| **Auth Provider** | [Neon Auth](https://neon.tech/docs/guides/neon-auth) (Better Auth) |
| **OAuth** | `@react-native-google-signin/google-signin` 16.x |
| **Animations** | React Native Reanimated 4.x |
| **Icons** | Lucide React Native |
| **Secure Storage** | React Native Keychain |
| **UI Effects** | `@react-native-community/blur`, Haptic Feedback |
| **Minimum Node** | ≥ 22.11.0 |

---

## 🏗 Architecture

```
┌────────────────────────────────────────────────────────┐
│                    React Native App                     │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐            │
│  │  Screens │──│Components│──│  Hooks    │            │
│  └────┬─────┘  └──────────┘  └───────────┘            │
│       │                                                │
│  ┌────▼──────────────────────────────────────┐        │
│  │          Redux Store (Toolkit)             │        │
│  │  ┌──────────┬──────────┬────────────┐     │        │
│  │  │ authSlice│themeSlice│workflowSlice│    │        │
│  │  └──────────┴──────────┴────────────┘     │        │
│  └────┬──────────────────────────────────────┘        │
│       │                                                │
│  ┌────▼──────────────────────────────────────┐        │
│  │          Services Layer                    │        │
│  │  ┌─────────┬──────────┬──────────────┐    │        │
│  │  │agentApi │authService│ httpClient   │    │        │
│  │  │calendarApi│dashboardApi│discoveryApi│   │        │
│  │  └─────────┴──────────┴──────────────┘    │        │
│  └────┬──────────────────────────────────────┘        │
│       │  Axios + JWT Interceptor                       │
└───────┼────────────────────────────────────────────────┘
        │  HTTPS
┌───────▼────────────────────────────────────────────────┐
│              SalesOps Agent Backend (FastAPI)           │
│       Multi-Agent Orchestrator (Google ADK)             │
│  ┌──────────┬──────────┬──────────┬──────────┐        │
│  │ LeadGen  │   CRM    │ Outreach │ Analysis │        │
│  │  Agent   │  Agent   │  Agent   │  Agent   │        │
│  └──────────┴──────────┴──────────┴──────────┘        │
│       │           │          │                         │
│  Google Places  ERPNext   Gmail / Google Calendar      │
└────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Authentication**: User signs in via Neon Auth → session token → exchanged for JWT → stored in Keychain
2. **Agent Chat**: User message → `POST /api/chat/stream` → backend orchestrator routes to sub-agents → streamed response replayed token-by-token in UI
3. **Calendar Sync**: Native Google Sign-In → `serverAuthCode` → `POST /api/calendar/sync` → backend exchanges for refresh token → encrypted & stored

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** ≥ 22.11.0
- **React Native CLI** — follow the official [Environment Setup](https://reactnative.dev/docs/set-up-your-environment)
- **Android**: Android Studio + SDK 35, JDK 17+
- **iOS**: Xcode 15+, CocoaPods (`gem install cocoapods`)
- **Backend**: [SalesOps Agent Backend](../salesops-agent-backend/) running locally or deployed

### Installation

1. **Clone the repository**
   ```sh
   git clone https://github.com/Sheikh-Muhammad-Mujtaba/AISeekho-challenge.git
   cd AISeekho-challenge/salesopsapp
   ```

2. **Install dependencies**
   ```sh
   npm install
   ```

3. **iOS only — install CocoaPods**
   ```sh
   bundle install                # First time only
   bundle exec pod install       # After every native dependency change
   ```

### Environment Variables

Copy the example and fill in your values:

```sh
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `API_URL` | Backend API base URL | `http://10.0.2.2:8000` (Android emu) or `http://localhost:8000` |
| `NEON_AUTH_URL` | Neon Auth endpoint for your branch | `https://ep-xxx.neonauth.xxx.neon.tech/neondb/auth` |
| `GOOGLE_WEB_CLIENT_ID` | Web OAuth Client ID from Google Cloud Console | `221249398234-xxx.apps.googleusercontent.com` |

> **Note:** For Android emulator, use `http://10.0.2.2:8000` instead of `localhost` to reach the host machine.

### Running the App

**Start Metro bundler:**
```sh
npm start
```

**Android:**
```sh
npm run android
```

**iOS:**
```sh
npm run ios
```

---

## 📂 Project Structure

```
salesopsapp/
├── App.tsx                     # Root component: Redux Provider + Navigation
├── src/
│   ├── components/             # Reusable UI components
│   │   ├── AuroraGradient.tsx   # Animated gradient backgrounds
│   │   ├── AuthInput.tsx        # Styled auth form inputs
│   │   ├── GlassCard.tsx        # Glassmorphism card component
│   │   ├── MetricCard.tsx       # Dashboard metric display
│   │   ├── NeonButton.tsx       # Primary action button with glow
│   │   ├── PlaybookCard.tsx     # Workflow playbook card
│   │   ├── QuickActionChip.tsx  # Home screen quick actions
│   │   ├── RecentActivity.tsx   # Activity feed component
│   │   └── WorkflowTimeline.tsx # Step-by-step workflow visualizer
│   ├── config.ts               # Runtime config from react-native-config
│   ├── constants/
│   │   └── icons.ts            # Lucide icon re-exports
│   ├── hooks/
│   │   └── useTheme.ts         # Theme hook (dark/light mode)
│   ├── navigation/
│   │   ├── index.tsx           # Auth gate: AuthStack ↔ AppStack
│   │   └── BottomTabs.tsx      # 4-tab navigator (Home, Agent, Alerts, Profile)
│   ├── screens/
│   │   ├── LoginScreen.tsx      # Email/password sign-in
│   │   ├── RegisterScreen.tsx   # New account registration
│   │   ├── HomeScreen.tsx       # Dashboard with metrics + quick actions
│   │   ├── ChatScreen.tsx       # AI agent chat with streaming
│   │   ├── NotificationScreen.tsx # System alerts
│   │   ├── AccountScreen.tsx    # Profile, theme toggle, calendar connection
│   │   ├── DiscoveryScreen.tsx  # Google Places business search
│   │   ├── CRMLeadsScreen.tsx   # ERPNext leads browser
│   │   ├── OutcomeDashboardScreen.tsx # Run outcome analytics
│   │   ├── TraceLogsScreen.tsx  # Agent execution traces
│   │   └── SimulationConsoleScreen.tsx # Sandbox testing
│   ├── services/
│   │   ├── httpClient.ts       # Axios instance + JWT interceptor
│   │   ├── authService.ts      # Neon Auth sign-in/up + JWT exchange
│   │   ├── agentApi.ts         # Agent chat + streaming replay
│   │   ├── calendarApi.ts      # Google Calendar sync/status/disconnect
│   │   ├── dashboardApi.ts     # Dashboard metrics + run history
│   │   ├── discoveryApi.ts     # Business discovery API
│   │   ├── authTokenStore.ts   # In-memory token holder
│   │   └── tokenPersistence.ts # Keychain read/write
│   ├── store/
│   │   ├── index.ts            # Redux store configuration
│   │   ├── hooks.ts            # Typed useAppSelector / useAppDispatch
│   │   └── slices/
│   │       ├── authSlice.ts    # Auth state (token, user, loading)
│   │       ├── themeSlice.ts   # Dark/light mode toggle
│   │       └── workflowSlice.ts # Active workflow tracking
│   ├── theme.ts                # Aurora Intelligence design tokens
│   └── types/
│       ├── auth.ts             # Auth-related TypeScript interfaces
│       └── env.d.ts            # react-native-config type declarations
├── android/                    # Android native project
├── ios/                        # iOS native project
├── .env.example                # Environment variable template
├── package.json                # Dependencies & scripts
└── tsconfig.json               # TypeScript configuration
```

---

## 📱 Screens

| Screen | Tab | Description |
|---|---|---|
| **Login / Register** | Auth Stack | Email & password authentication via Neon Auth |
| **Home** | 🏠 Home | Dashboard with metrics, quick-action chips, playbook cards, and recent activity |
| **Chat** | 💬 Agent | Full-screen AI agent chat with real-time streaming, tool-step indicators |
| **Notifications** | 🔔 Alerts | System notifications for completed workflows and events |
| **Account** | 👤 Profile | User info, dark/light theme toggle, Google Calendar connect/disconnect |
| **Discovery** | Deep Screen | Search businesses via Google Places, view details, create CRM leads |
| **CRM Leads** | Deep Screen | Browse and manage ERPNext CRM leads |
| **Outcome Dashboard** | Deep Screen | Per-run analytics with agent steps and outcomes |
| **Trace Logs** | Deep Screen | Detailed execution traces for agent debugging |
| **Simulation Console** | Deep Screen | Test agent workflows in sandbox mode |

---

## 🗃 State Management

The app uses **Redux Toolkit** with three slices:

| Slice | Responsibilities |
|---|---|
| `authSlice` | JWT token, user profile, session restore from Keychain, login/logout |
| `themeSlice` | Dark/light mode preference |
| `workflowSlice` | Active workflow run tracking |

Session persistence uses **React Native Keychain** — tokens are stored encrypted in the device's secure enclave and restored automatically on app launch.

---

## 🔌 API Services

| Service | Backend Endpoint | Purpose |
|---|---|---|
| `authService` | `{NEON_AUTH_URL}/api/auth/*` | Sign-in, sign-up, JWT exchange |
| `agentApi` | `POST /api/chat/stream` | Agent conversation with streaming replay |
| `calendarApi` | `/api/calendar/*` | Google Calendar sync, status check, disconnect |
| `dashboardApi` | `/api/dashboard/*` | Metrics, run history |
| `discoveryApi` | `/api/discovery/*` | Business search via Google Places |

All services use a shared `httpClient` (Axios) with automatic JWT injection via request interceptors and 401 auto-logout handling.

---

## 🎨 Design System

The app uses the **Aurora Intelligence** design system with dual-theme support:

| Token | Dark Mode | Light Mode |
|---|---|---|
| Background | `#07111F` (deep navy) | `#F8F9FC` (clean white) |
| Primary | `#6D5CFF` (aurora violet) | `#5B57FF` |
| Accent | `#36CFFF` (cyan glow) | `#28B7FF` |
| Accent Green | `#2BE4B8` (teal) | `#14D7B0` |
| Surface | `#0D1728` | `#FFFFFF` |

**Design components** include glassmorphism cards, aurora gradient backgrounds, neon-glow buttons, and haptic feedback on interactions.

---

## 🔗 Backend Integration

This app requires the **SalesOps Agent Backend** to function. The backend provides:

- **Multi-Agent AI Orchestrator** — Google ADK with specialized sub-agents
- **Neon Auth** — JWT-based authentication via Neon Postgres
- **Google Calendar API** — Real OAuth token exchange and event management
- **ERPNext CRM** — Lead CRUD operations
- **Google Places API** — Business discovery and enrichment
- **Gmail SMTP** — Real email sending (no simulation)

See the [backend README](../salesops-agent-backend/README.md) for setup instructions.

---

## 🔒 Security

- **JWT Authentication** — All API requests include a Bearer token via Axios interceptors
- **Secure Token Storage** — Tokens stored in device Keychain (iOS) / Keystore (Android) via `react-native-keychain`
- **OAuth Code Exchange** — Google `serverAuthCode` is exchanged server-side; client never sees the refresh token
- **No Hardcoded Secrets** — All credentials loaded from `.env` via `react-native-config`
- **Auto Logout** — 401 responses trigger automatic session cleanup and redirect to login

---

## ⚠️ Known Limitations

- **Streaming UX** — The backend returns a buffered JSON response rather than true SSE; the app simulates streaming by replaying tokens client-side
- **Offline Mode** — No offline caching or queue; requires active network connection
- **iOS Calendar** — Google Sign-In on iOS requires a correctly configured URL scheme in Xcode's `Info.plist`
- **Android Emulator** — Use `http://10.0.2.2:8000` as `API_URL` to reach the host machine's localhost
- **Theme Persistence** — Theme preference resets on app restart (stored in Redux, not persisted)

---

<p align="center">
  Built with ❤️ using React Native &amp; TypeScript
  <br />
  Part of the <strong>AISeekho Challenge</strong>
</p>
