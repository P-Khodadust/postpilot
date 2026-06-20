# Deployment

## 0. Prerequisites
- A public HTTPS origin (`PUBLIC_BASE_URL`) reachable by Telegram, X, and Stripe.
- Docker + Docker Compose (or any container host). PostgreSQL 16 + Redis 7 (compose provides both).

## 1. Register an X (Twitter) app
1. Create a project + app in the X developer portal. **Confirm your tier's monthly post cap and price** — this is the real constraint; set `X_APP_MONTHLY_POST_CAP` to it.
2. Enable OAuth 2.0, type **Web App / Confidential client**.
3. Set the callback / redirect URL to `${PUBLIC_BASE_URL}/oauth/x/callback`.
4. Scopes: `tweet.read tweet.write users.read offline.access`.
5. Copy the client id + secret → `X_CLIENT_ID`, `X_CLIENT_SECRET`.

## 2. Telegram bot
1. Create a bot with @BotFather → `TELEGRAM_BOT_TOKEN`.
2. Pick a random `TELEGRAM_WEBHOOK_SECRET` (32+ chars). Webhook mode is set automatically by the `bot` process on boot to `${PUBLIC_BASE_URL}/telegram/webhook`.
3. For local dev without a public URL, set `TELEGRAM_USE_WEBHOOK=false` (long-polling, single replica).

## 3. Secrets
```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # TOKEN_ENC_KEYS
```
Fill: `TOKEN_ENC_KEYS` (newest first, comma-separated for rotation), `ANTHROPIC_API_KEY`,
`STRIPE_API_KEY` + `STRIPE_WEBHOOK_SECRET`, `ADMIN_SESSION_SECRET`, `DATABASE_URL`, `REDIS_URL`.
In production the app **fails fast** if required secrets are missing.

## 4. Stripe (optional now, abstracted)
- Create products/prices; map to plan codes.
- Add a webhook endpoint → `${PUBLIC_BASE_URL}/billing/stripe/webhook` (signing secret → `STRIPE_WEBHOOK_SECRET`).

## 5. Run
```bash
docker compose up --build -d
docker compose logs -f migrate        # confirm it exited 0
curl -fsS http://localhost:8000/healthz
docker compose up -d --scale worker=3 # scale the sender
```
Migrations run only via the `migrate` container; app processes never auto-migrate.

## 6. Create an admin user
```bash
docker compose run --rm web python - <<'PY'
import asyncio
from postpilot.core.db import session_scope
from postpilot.models import AdminUser
from postpilot.web.admin.auth import hash_password
async def main():
    async with session_scope() as s:
        s.add(AdminUser(email="you@example.com", password_hash=hash_password("change-me"), role="superadmin"))
asyncio.run(main())
PY
```
Then visit `${PUBLIC_BASE_URL}/admin/login`.

## 7. Token-key rotation
Prepend a new Fernet key to `TOKEN_ENC_KEYS` (comma-separated, newest first), redeploy. Old ciphertext
still decrypts (MultiFernet); a background re-encrypt can roll rows to the new key.

## 8. Verify end-to-end
See the "Verification" section of the project plan: OAuth round-trip on a test X app, a 2-minute
scheduled post that fires exactly once, Stripe test-mode checkout → entitlement change, and the
tenant-isolation test.
