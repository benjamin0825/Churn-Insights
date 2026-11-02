# Churn Insights by WSL Technologies

A churn prediction service for subscription businesses. Companies load their customer data, and
the service predicts who is likely to leave in the next 8 weeks, explains why, and plans retention
campaigns that maximize expected profit.

Built on the [`churn_ml`](../AI%20Machine%20Learning) platform: point-in-time features, a tuned and
calibrated model ensemble, SHAP explanations, a model registry and drift monitoring.

## Features

| Area | What it does |
|---|---|
| **Website** | Public home, pricing and jobs pages at `/`, `/pricing` and `/jobs`; the signed-in app lives under `/app` |
| **About** | Company story, mission, values and the team (Leadership first, then Engineering and other teams) with photos and links; all managed in the admin panel |
| **Careers** | Job postings with an application form (CV upload, links, cover note); spam honeypot and per-address rate limit |
| **Admin panel** | `/admin` for site operators: sign-up and activity overview, every workspace (plan, suspend, delete), every user (role, disable, reset password, admin access), background jobs across workspaces (clear stuck jobs), the plans shown on the pricing page, the About page (company text, team members and photos), and hiring (write and publish job postings, review applications, download CVs, track status and notes) |
| **Accounts** | Self-service sign-up creates an organization; every query and file is isolated per organization |
| **Data** | Upload four CSVs (customers, weekly usage, invoices, support tickets) with validation and readable errors, or load realistic demo data in one click; downloadable templates |
| **Dashboard** | Active customers, high-risk count, expected churners, revenue at risk, risk tiers, churn trend, risk by region and contract, top churn drivers, model health |
| **Customers** | Searchable, filterable, sortable risk list; detail page with the 8 strongest reasons (SHAP), key signals, 52-week usage, tickets and invoices |
| **Campaigns** | Set offer cost, success rate, customer value, budget and tiers; see targets, cost, expected revenue saved, profit, ROI and a profit curve live; save and export target lists as CSV |
| **Models** | Train new versions (quick / standard / thorough), compare model families, open the full HTML report, promote or roll back; champion vs challenger keeps a worse model out of production |
| **Monitoring** | Drift per feature (PSI and KS tests), prediction drift, and drift per region, which catches local shocks that global numbers hide |
| **Settings** | Default campaign economics, light / dark / system theme |

## Architecture

```
frontend/   React 19 + TypeScript + Vite, TanStack Query, React Router, Recharts, Tailwind CSS
backend/    FastAPI + SQLAlchemy (SQLite), JWT auth, background job runner
            └─ churn_ml (sibling repository): features, models, registry, SHAP, drift
```

- Each organization's data lives under `backend/data/orgs/org_<id>/`: raw tables, feature cache,
  model registry, latest scores, drift reports and campaign exports.
- Training, scoring and drift checks run as **background jobs** (thread pool). The UI polls job
  status and refreshes itself when a job finishes. Each organization runs one heavy job at a time.
- In production the backend also serves the built frontend (`frontend/dist`), so it deploys as
  **one service**. The API is under `/api`, with interactive docs at `/api/docs`.

## Requirements

- **Python 3.14** (the bundled native engine in `churn_ml` targets CPython 3.14; other versions
  fall back to slower NumPy kernels)
- **Node.js 20+** (tested with 24 LTS), only needed to build the frontend

## Setup

```powershell
# backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# frontend
cd ..\frontend
npm install
npm run build
```

## Running

**Production-style (one server):**

```powershell
.\start.ps1          # builds the frontend if needed, then serves http://127.0.0.1:8000
```

**Development (hot reload):**

```powershell
# terminal 1
cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend; npm run dev          # http://localhost:5173, proxies /api to :8000
```

Open the app, create a workspace, click **Load demo data**, and the dashboard appears in about a
minute.

## Admin panel

Admin access is never granted by sign-up. Give it to an account from the server:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli make-admin you@example.com      # an existing account
.\.venv\Scripts\python.exe -m app.cli create-admin you@example.com "Your Name"   # new account, asks for a password
.\.venv\Scripts\python.exe -m app.cli list-admins
.\.venv\Scripts\python.exe -m app.cli revoke-admin someone@example.com
```

Then sign in and open **Admin** in the sidebar (or go to `/admin`). Admins can also grant admin
access to other users from the Users screen. Suspending a workspace or disabling a user locks them
out immediately. Plans are labels for now: nothing is charged and no limits are enforced.

**Hiring:** postings start as drafts and appear on `/jobs` once published; closing one keeps its
link working but stops applications. CVs (PDF or Word, up to 5 MB, checked by content) are stored
under `DATA_DIR/applications` with random file names and can only be downloaded by admins. No email
is sent; check **Admin → Hiring** for new applications.

Existing databases are upgraded automatically on start (new columns and a `plans` table seeded
with Starter, Growth and Scale).

## Configuration

Environment variables (or `backend/.env`), all prefixed `CHURN_SERVICE_`:

| Variable | Default | |
|---|---|---|
| `DATA_DIR` | `backend/data` | Database, secret key and per-organization files |
| `SECRET_KEY` | generated into `DATA_DIR/secret.key` | JWT signing key; **set it explicitly in production** |
| `TOKEN_TTL_MINUTES` | `720` | Login session length |
| `MAX_UPLOAD_MB` | `300` | Per-file upload limit |
| `CORS_ORIGINS` | `["http://localhost:5173", ...]` | Allowed browser origins for the dev server |
| `JOB_WORKERS` | `2` | Parallel background jobs |
| `MIN_HISTORY_WEEKS` | `52` | Minimum history an upload must cover |

## Upload format

Download templates from the **Data** page. Dates can use any common format; booleans accept
`true/false`, `yes/no` or `1/0`.

| File | Columns |
|---|---|
| `customers.csv` | customer_id, signup_date, age, region, plan, internet_service, has_streaming, contract_type, payment_method, paperless_billing, dependents, acquisition_channel, churn_date (empty if active) |
| `usage.csv` | customer_id, week_start, sessions, minutes, data_gb |
| `billing.csv` | customer_id, invoice_date, amount, discount_pct, paid_late, days_late |
| `tickets.csv` | customer_id, created_at, category, text, resolution_hours, csat |

## Tests

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest     # 35 end-to-end API tests, about 30 s
cd frontend; npm run build; npm run lint             # type check, production build, lint
```

The backend tests cover registration and login, auth on every endpoint, tenant isolation, demo
data, training, dashboard, customer list and detail, campaigns (budget, export, delete), model
versions and reports, drift, CSV upload, rejection of malformed uploads, and the admin panel
(access control, suspend, disable, password reset, stuck jobs, plans, delete, schema upgrade), and
careers (drafts, publishing, applications, CV checks, spam protection), and the About page
(profile, team order and visibility, photo checks).

## Version 1 limitations

These are known gaps to close before offering the service to real customers:

- **Fixed data schema.** Categories (region, plan, contract, and so on) follow the telecom /
  broadband schema. Other industries need a configurable column mapping.
- **Auth basics only.** No email verification, self-service password reset, invitations, SSO or
  rate limiting (admins can reset a password by hand).
  Tokens are kept in `localStorage`; httpOnly cookies with CSRF protection would be safer.
- **Single node.** SQLite and an in-process job runner suit one server. Scaling out needs Postgres,
  a job queue (for example Celery or RQ) and shared file storage (for example S3).
- **No scheduled retraining or alerts.** Drift and training run on demand.
- **Real data obligations.** Hosting customer data requires a privacy and security review
  (GDPR / CCPA, encryption at rest, retention policy, data processing agreements).
