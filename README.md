<div align="center">

```
            ╔═══════════════════════════════════╗
            ║   ✈   P O S T   P I L O T         ║
            ╚═══════════════════════════════════╝
```

# Your X account, on autopilot — from the one app you never close.

**PostPilot** is a Telegram-native SaaS that posts to X (Twitter) *for* you.
Connect once, tell it your hours, and it keeps your feed alive — recurring announcements,
one-off posts, rotating wording — without you ever opening Twitter.

<br/>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](#)
[![aiogram](https://img.shields.io/badge/aiogram-3-26A5E4?style=flat-square&logo=telegram&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](#)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/status-early%20access-f59e0b?style=flat-square)](#-status--roadmap)

<a href="#-see-it-in-action">Demo</a> ·
<a href="#-features">Features</a> ·
<a href="#%EF%B8%8F-how-it-works">How it works</a> ·
<a href="#-quick-start">Quick start</a> ·
<a href="#-architecture">Architecture</a>

</div>

---

## 💬 See it in action

No dashboard. No logins. Just a chat:

```text
  you  ▸  /start

  ✈    ▸  Welcome to PostPilot. I keep your X account active automatically.
          Set it up once, I post for you. Ready?
          ┌──────────────────────┐
          │  ✨ Let's set it up   │
          └──────────────────────┘

  you  ▸  ✨ Let's set it up  →  🔗 Connect my X account
          (authorize in the browser, come back)

  ✈    ▸  ✅ Connected as @yourcafe.  When are you open?
          [ Mon ✓ ] [ Tue ✓ ] [ Wed ✓ ] [ Thu ✓ ] [ Fri ✓ ] [ Sat ✓ ] [ Sun ✗ ]

  you  ▸  open 8:00   ·   close 18:00

  ✈    ▸  🎉 All set. Every morning I'll post "We're open!", every evening
          "Closed for today" — rotating the wording so X never sees a repeat.
          You'll never tweet your opening hours by hand again.
```

---

## 🧠 The idea

Small-business owners *want* an active X presence. They do **not** want another dashboard,
another password, another tab. But they already live in Telegram.

So PostPilot meets them there. It speaks human, posts on schedule, and connects to X the
**right** way — the official API with real OAuth.

> **No passwords. No cookies. No scraping.** Users authorize through X's own login (OAuth 2.0 + PKCE);
> tokens are encrypted at rest, auto-refreshed, and wiped on disconnect. Built to be *sold*, not to get banned.

---

## ✨ Features

| | |
|--|--|
| 🔗 **One-tap connect** | Official X OAuth 2.0 (PKCE). Encrypted tokens, auto-refresh + rotation, revoke-on-disconnect. |
| 🌓 **Open / Close on autopilot** | Per-weekday times, timezone-aware, with **variant rotation** so X never flags a duplicate. |
| ✍️ **Post anything, anytime** | Compose one-offs, schedule for later, or fire instantly — from the chat. |
| 🧭 **A wizard, not a manual** | Five friendly steps. Zero jargon. Built for people who don't know what "OAuth" means. |
| 🤖 **AI assist** *(optional)* | Claude writes on-brand captions & plain-English insights. Stats computed in code, never hallucinated. |
| 💳 **Plans & limits** | Free / Starter / Pro behind a pluggable provider — Stripe **and** Telegram Stars. |
| 🛡️ **Multi-tenant, safely** | Row-level isolation enforced by an ORM guard that *fails the build* on an unscoped query. |
| 🔁 **Exactly-once posting** | A Postgres `SKIP LOCKED` lease loop. Scale workers horizontally; never double-post. |
| 📊 **Admin dashboard** | FastAPI + HTMX: KPIs, accounts, subscriptions, queue health. |
| 🐳 **One command to run it all** | One image, four roles, `docker compose up`. |

---

## ⚙️ How it works

```
   ①  Connect          ②  Schedule              ③  Relax
   ───────────         ─────────────            ──────────
   Tap "Connect X"  →  Pick your days/times  →  PostPilot queues, posts,
   authorize once      & let AI draft copy      rotates wording, retries,
   (real OAuth)        (or write your own)      and pings you when it's live
```

Every post — even "post now" — flows through a durable queue, so retries, back-off,
idempotency and rate-limits are uniform, and adding more workers can never cause a double-post.

---

## 🏗️ Architecture

One Docker image, four roles, sharing **PostgreSQL** + **Redis**:

```
  Telegram ─webhook─►┌──────────────────────────────┐
  X OAuth  ─────────►│  web · FastAPI               │  /oauth/x/callback
  Stripe   ─────────►│  callbacks · webhooks · admin│  /telegram/webhook · /admin
                     └───────────────┬──────────────┘
       bot · aiogram ────────────────┤
       onboarding · menus · FSM       ▼
                            PostgreSQL 16  ◄──►  Redis 7
       worker ×N ─ SKIP LOCKED lease ─┘          FSM · locks · rate-limit
       send · materialize · refresh
                     migrate · Alembic (one-shot, gates the rest)
```

<sub>Exactly-once delivery comes from the **database**, not the process — so `--scale worker=N` stays correct.</sub>

---

## 🚀 Quick start

```bash
git clone https://github.com/P-Khodadust/postpilot.git && cd postpilot
cp .env.example .env

# generate a token-encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# drop TELEGRAM_BOT_TOKEN, X_CLIENT_ID/SECRET, TOKEN_ENC_KEYS into .env, then:
docker compose up --build          # migrate runs once → web :8000/healthz → bot + worker live
docker compose up -d --scale worker=3
```

Production setup (X app, OAuth redirect, HTTPS, webhooks) → **[DEPLOYMENT.md](DEPLOYMENT.md)**.

---

## 🧰 Built with

![aiogram](https://img.shields.io/badge/aiogram_3-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Postgres](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis_7-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

<details>
<summary><b>📂 Project layout</b></summary>

```
src/postpilot/
├─ core/         settings · async DB · Redis · token crypto · errors · logging
├─ models/       SQLAlchemy schema (19 tables) + TenantScoped mixin
├─ tenancy/      TenantContext · scoping repo · isolation guard · RBAC
├─ x_api/        OAuth 2.0 PKCE · tweet client (retry / 429)
├─ scheduler/    lease worker · materializer · reclaim · token refresh · rotation
├─ billing/      PaymentProvider · Stripe · Telegram Stars · plan seeding
├─ entitlements/ check_quota at every action boundary
├─ metering/ · ai/ · notifications/
├─ bot/          runtime · middleware · handlers · keyboards · i18n
└─ web/          app · routes · admin (Jinja + HTMX)
docker/ · alembic/ · tests/{unit,integration,fakes}
```
</details>

<details>
<summary><b>🧪 Develop & test</b></summary>

```bash
pip install -e ".[dev]"
ruff check . && mypy src
pytest                 # unit tests; integration tests spin up Postgres via testcontainers
```
See **[CONTRIBUTING.md](CONTRIBUTING.md)** and **[ARCHITECTURE.md](ARCHITECTURE.md)**.
</details>

<details>
<summary><b>🌱 Why I built this</b></summary>

It started as a 30-line script to auto-tweet "we're open" for one shop owner who was tired of
doing it by hand. The script kept growing — variants so X wouldn't flag duplicates, then scheduling,
then "could other people use this?" — until it became a real, multi-tenant product. PostPilot is that
rabbit hole, cleaned up and open-sourced.
</details>

---

## 🗺️ Status & roadmap

PostPilot is **early access** — the core is built and tested; some surfaces are still filling in. Honest checklist:

- [x] Telegram bot, onboarding wizard, menus (polling-ready)
- [x] X OAuth 2.0 (PKCE) + encrypted token store
- [x] `SKIP LOCKED` scheduler, variant rotation, retries
- [x] Plans, quotas, multi-tenant isolation, Docker, CI, tests
- [ ] HTTPS callback wiring for one-click "Connect X" in hosted mode
- [ ] Stripe / Telegram billing flows end-to-end
- [ ] Full admin dashboard (queue monitor, plan editor)

Contributions welcome — open an issue or a PR.

---

## ⚠️ Heads-up on X API costs

X API write access is **paid and tiered**, and the per-project monthly post cap is **shared across all
tenants**. Free is fine for testing; a real launch needs a paid tier. PostPilot treats the cap as config
and degrades gracefully (queue, back-off, notify) — confirm current X pricing before going commercial.

---

<div align="center">

**[MIT](LICENSE)** · made with too much coffee ☕ and a Telegram bot that wouldn't stop growing

<sub>If this is useful, a ⭐ means a lot.</sub>

</div>
