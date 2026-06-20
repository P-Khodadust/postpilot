# Architecture

## Processes (one Docker image, role chosen by `entrypoint.sh`)
- **web** — FastAPI/Uvicorn: `/oauth/x/callback`, `/telegram/webhook`, `/billing/stripe/webhook`, `/healthz`, `/admin/*`.
- **bot** — aiogram v3 dispatcher (webhook mode: web feeds updates; polling mode for single-replica dev).
- **worker** — the post pipeline: lease due rows, send via X API, record history; also materializes schedules, refreshes tokens, dispatches notifications.
- **migrate** — one-shot `alembic upgrade head`, gates the others.

Shared **PostgreSQL 16** (durable state + the scheduler's exactly-once primitive) and **Redis 7**
(aiogram FSM, rate-limit token buckets, materializer leader lock, OAuth state TTL).

```
Telegram/X/Stripe ─► web (FastAPI) ─┐
                                     ├─► PostgreSQL ◄─ worker (SKIP LOCKED lease loop, xN)
        bot (aiogram) ──────────────┘        ▲
                                      Redis ──┘
```

## Source layout (`src/postpilot/`)
- `core/` — settings, async DB, Redis, token crypto (MultiFernet), typed errors, structured logging.
- `models/` — SQLAlchemy 2.0 models + `TenantScoped` mixin.
- `tenancy/` — `TenantContext`, `TenantRepo` (account-scoped queries), `do_orm_execute` isolation guard, RBAC.
- `x_api/` — OAuth PKCE (`oauth.py`) + tweet client with retry/429 handling (`client.py`).
- `scheduler/` — `rotation.py` (pure), `materializer.py`, `worker.py` (lease loop), `reclaim.py`, `token_refresh.py`.
- `billing/` — `PaymentProvider` protocol + Stripe & Telegram implementations + plan seeding.
- `entitlements/` — plan/limit definitions + `check_quota` / `assert_can_connect_x`.
- `metering/` — usage events, monthly counters, rollups.
- `ai/` — Claude client (tier routing, prompt caching, fallbacks), prompts, guardrails.
- `notifications/` — enqueue + Telegram dispatch.
- `bot/` — runtime, tenant middleware, FSM states, keyboards, i18n, handlers (onboarding/connect/schedules/posts/insights/billing/core).
- `web/` — FastAPI app, routes, admin (Jinja + HTMX).
- `worker/` — worker process loop.

## Key invariants
1. **Exactly-once posting** = Postgres `UPDATE … WHERE id IN (SELECT … FOR UPDATE SKIP LOCKED)`; safe across N worker replicas. Not Celery/APScheduler job stores.
2. **All posting is async** through `post_queue` (even "post now") so retry/backoff/idempotency/metering are uniform. `idempotency_key` (unique per tenant) prevents double-posts.
3. **Refresh-token rotation is atomic** — X invalidates the old refresh token on every refresh; the new one is persisted in the same transaction (`scheduler/token_refresh.py`).
4. **Tenant isolation** — every tenant table carries `account_id`; reads go through `TenantRepo`; the ORM guard raises on unscoped tenant SELECTs in strict mode (tests/CI).
5. **Tokens encrypted at rest** (versioned MultiFernet); decrypted only at call time; deleted on disconnect.
6. **AI never invents stats** — analytics computed in code and passed as DATA; the model only narrates; failures fall back to templated copy.

## Schema (Alembic `0001_initial`, created from model metadata)
Identity: `accounts`, `tg_users`, `memberships` (role: owner/admin/member/viewer).
X: `connected_x_accounts` (encrypted tokens), `oauth_states` (PKCE, TTL).
Scheduling: `recurring_schedules` (config JSONB), `message_variants` (rotation cursor), `post_queue` (leasing), `post_history`.
Billing: `plans`, `plan_limits`, `subscriptions`, `billing_events` (webhook idempotency).
Metering: `usage_counters`, `usage_events`, `platform_daily_metrics`.
Ops: `audit_log`, `notifications`, `admin_users`.
