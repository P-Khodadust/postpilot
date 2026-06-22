<div align="center">

# 🛩️ PostPilot

### Schedule your X (Twitter) presence from Telegram — no dashboards, no logins, no fuss.

A multi-tenant **Telegram-bot SaaS** that auto-posts to X for busy business owners:
recurring *"we're open / we're closed"* announcements, one-off scheduled posts, and rotating
wording so your feed never goes quiet — all driven from a chat, built on the **official X API + OAuth**.

<br/>

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## ✨ Why PostPilot

Most small-business owners want their X account active but don't want to babysit a scheduling
dashboard. PostPilot lives in **Telegram** — the app they already have open — and posts for them
on a schedule. Connect once with a tap (real OAuth, never a password or cookie), set your hours,
and it handles the rest.

> **Built the right way for resale:** users authorize via the **official X API v2 (OAuth 2.0 + PKCE)**.
> No scraping, no stored passwords, no fragile browser hacks — just least-privilege tokens, encrypted at rest.

## 🚀 Features

| | |
|---|---|
| 🔗 **One-tap X connect** | OAuth 2.0 (PKCE). Tokens encrypted at rest (MultiFernet), auto-refreshed & rotated, revoked on disconnect. |
| 🌓 **Open / Close schedules** | Per-weekday times, timezone-aware, with **message-variant rotation** so X never sees a duplicate. |
| ✍️ **One-off posts** | Compose and schedule (or post now) straight from the chat. |
| 🧭 **Guided onboarding** | A friendly 5-step wizard — no jargon, built for non-technical owners. |
| 🤖 **AI assist** *(optional)* | Claude-powered caption variants & insights — code-computed stats, never hallucinated. Toggle with one flag. |
| 💳 **Plans & limits** | Free / Starter / Pro tiers behind a pluggable `PaymentProvider` (Stripe + Telegram Stars). |
| 🛡️ **Multi-tenant by design** | Strict row-level isolation with an ORM guard that *fails the build* on an unscoped query. |
| 📊 **Admin dashboard** | FastAPI + Jinja + HTMX: KPIs, accounts, subscriptions, queue health. |
| 🔁 **Exactly-once posting** | Postgres `SKIP LOCKED` lease loop — horizontally scalable workers, no double-posts. |
| 🐳 **One-command deploy** | Single Docker image, four roles, `docker compose up`. |

## 🏗️ Architecture

One image, four roles, sharing **PostgreSQL** + **Redis**:

```
 Telegram ─webhook─►┌─────────────────────────────┐
 X OAuth  ─────────►│  web  (FastAPI)             │  /oauth/x/callback
 Stripe   ─────────►│  OAuth · webhooks · admin   │  /telegram/webhook
                    └──────────────┬──────────────┘  /billing/* · /admin
      bot (aiogram) ───────────────┤
      onboarding · menus · FSM     ▼
                          PostgreSQL 16  ◄──►  Redis 7
      worker (×N) ─ SKIP LOCKED lease ─┘        (FSM · locks · rate-limit)
      send · materialize · refresh tokens
                    migrate ─ Alembic (one-shot)
```

The posting pipeline is **always asynchronous** (everything flows through a `post_queue`), so retries,
back-off, idempotency, and metering are uniform — and `--scale worker=N` stays correct because exactly-once
comes from the database, not the process.

## ⚡ Quick start (local)

```bash
git clone https://github.com/P-Khodadust/postpilot.git && cd postpilot
cp .env.example .env

# generate a token-encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # -> TOKEN_ENC_KEYS

# fill TELEGRAM_BOT_TOKEN, X_CLIENT_ID/SECRET, TOKEN_ENC_KEYS in .env, then:
docker compose up --build            # migrate runs once; web :8000/healthz, bot + worker start
docker compose up -d --scale worker=3
```

Full production setup (X app, OAuth redirect, HTTPS, webhooks) → **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## 🧰 Tech stack

**aiogram 3** (bot) · **FastAPI** (web/admin/OAuth) · **SQLAlchemy 2.0 async + Alembic** ·
**PostgreSQL 16** · **Redis 7** · **httpx** · **Anthropic Claude** · **Stripe / Telegram Payments** ·
**Docker** · **pytest + testcontainers** · **ruff + mypy**.

## 📂 Project layout

```
src/postpilot/
├─ core/         settings · async DB · Redis · token crypto · errors · logging
├─ models/       SQLAlchemy schema (19 tables) + TenantScoped mixin
├─ tenancy/      TenantContext · scoping repo · isolation guard · RBAC
├─ x_api/        OAuth 2.0 PKCE · tweet client (retry/429)
├─ scheduler/    lease worker · materializer · reclaim · token refresh · rotation
├─ billing/      PaymentProvider · Stripe · Telegram · plan seeding
├─ entitlements/ check_quota at every action boundary
├─ metering/ · ai/ · notifications/
├─ bot/          runtime · middleware · handlers · keyboards · i18n
└─ web/          app · routes · admin (Jinja + HTMX)
docker/ · alembic/ · tests/{unit,integration,fakes}
```

## 🔬 Development

```bash
pip install -e ".[dev]"
ruff check . && mypy src
pytest                 # unit tests; integration tests use testcontainers (need Docker)
```

See **[CONTRIBUTING.md](CONTRIBUTING.md)** · architecture deep-dive in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## ⚠️ A note on X API costs

X API write access is **paid and tiered**, and the per-project monthly post cap is **shared across all
tenants**. The Free tier is fine for testing and very low volume; a real multi-tenant launch needs a paid
tier. PostPilot treats the cap as config (`X_APP_MONTHLY_POST_CAP`) and degrades gracefully (queues, backs
off, notifies) — but confirm current X pricing before going commercial.

## 📜 License

[MIT](LICENSE) © PostPilot

<div align="center"><sub>Built to run lean — Telegram-native, OAuth-correct, container-ready.</sub></div>
