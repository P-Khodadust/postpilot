# syntax=docker/dockerfile:1
# ---- Builder ----
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# ---- Runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
# Normalize line endings (defends against CRLF from Windows checkouts) then make executable.
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh && chown -R app:app /app
USER app
ENTRYPOINT ["entrypoint.sh"]
CMD ["web"]
