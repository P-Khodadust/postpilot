# 🛩 PostPilot

A commercial, multi-tenant **Telegram-bot SaaS** that schedules and posts to X (Twitter) for
non-technical business owners — "we're open / we're closed" and any other posts — on a schedule,
with rotating wording, AI-written captions, and analytics.

Built on the **official X API v2 with OAuth 2.0** (users click "Connect X" and authorize; we never
touch passwords or cookies). Production-grade: typed, tested, migrated, observable, Dockerized.

> ⚠️ **X API is paid and tiered, and the per-project monthly post cap is shared across all tenants.**
> Free tier is testing-only; Basic/Pro tiers are required for real volume. PostPilot treats the cap
> as config (`X_APP_MONTHLY_POST_CAP`) and degrades gracefully (queues, backs off, notifies users),
> but you must confirm current X pricing/limits before a paid launch. This is the gating business cost.

## What it does
- **Connect X** via OAuth (encrypted tokens, refresh-rotation, revoke-on-disconnect).
- **Recurring open/close posts** with per-weekday times and message-variant rotation (so X never sees a duplicate).
- **One-off scheduled posts** ("post now" or later).
- **AI** (Claude): write/rewrite on-brand captions, best-time-to-post tips, weekly summaries — stats computed in code, never hallucinated.
- **Notifications**: posted/failed alerts, daily digest, reminders, usage/billing nudges.
- **Billing**: Free/Starter/Pro plans with usage limits, behind a `PaymentProvider` abstraction (Stripe + Telegram Payments/Stars).
- **Admin dashboard**: KPIs, accounts, subscriptions, queue/health (FastAPI + Jinja + HTMX).

## Architecture (one image, four roles)
`web` (FastAPI: OAuth callback, Telegram & billing webhooks, admin) · `bot` (aiogram v3) ·
`worker` (Postgres `SKIP LOCKED` lease loop — exactly-once, horizontally scalable) · `migrate` (Alembic).
Shared **PostgreSQL** + **Redis**. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick start (local)
```bash
cp .env.example .env       # fill TELEGRAM_BOT_TOKEN, X_CLIENT_ID/SECRET, TOKEN_ENC_KEYS, ANTHROPIC_API_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> TOKEN_ENC_KEYS
docker compose up --build
# migrate runs once; web on :8000 (/healthz), bot + worker start.
docker compose up --scale worker=3   # scale the sender; still exactly-once
```
Full setup (X app, redirect URI, webhooks) in [DEPLOYMENT.md](DEPLOYMENT.md).

## Develop
```bash
pip install -e ".[dev]"
ruff check . && mypy src
pytest                      # unit tests; integration tests use testcontainers (need Docker)
```
See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
