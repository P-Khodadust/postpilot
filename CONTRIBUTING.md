# Contributing

## Dev setup
```bash
python -m venv .venv && . .venv/bin/activate    # (Windows: .venv\Scripts\activate)
pip install -e ".[dev]"
```
Python 3.12 is the target runtime (the Docker images pin 3.12). Use it locally to match CI.

## Quality gates (run before pushing)
```bash
ruff check . && ruff format --check .
mypy src
pytest --cov                         # unit tests always; integration needs Docker
```
CI (`.github/workflows/ci.yml`) runs lint, types, unit + integration (testcontainers Postgres/Redis),
Alembic up/down reversibility, a Docker build, and a Trivy scan.

## Conventions
- **Tenant safety:** never `select(Model)` a tenant table in feature code — go through `TenantRepo`. The `do_orm_execute` guard raises in strict mode if you forget.
- **Posting:** never call the X API directly from a handler — enqueue to `post_queue`; the worker owns retry/backoff/idempotency.
- **Secrets:** never log tokens; add new secrets to `core/config.Settings` + `.env.example`.
- **Migrations:** `alembic revision --autogenerate -m "..."`, review the diff, ensure `downgrade` is real.
- **AI:** compute any number in code and pass it as DATA; the model only narrates. Always provide a templated fallback.

## Tests
- Unit tests live in `tests/unit/` (pure logic, no I/O) and gate every PR.
- Integration tests in `tests/integration/` spin up ephemeral Postgres via testcontainers; they
  auto-skip if Docker/testcontainers is unavailable. Target: 85%+ overall, 100% on tenancy/billing/crypto.
- Use the fakes in `tests/fakes/` (`FakeXClient`) and `stripe-mock` for external services.
