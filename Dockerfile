# Committed in Phase 0, exercised from Phase 7. Kept in sync deliberately so the
# container build never becomes a big-bang surprise at deploy time.
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer first so source edits do not invalidate the resolved set.
COPY pyproject.toml uv.lock ./
COPY packages/makeover-contracts/pyproject.toml packages/makeover-contracts/
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health').read()"

CMD ["uv", "run", "--no-dev", "uvicorn", "makeover_discovery.interfaces.api.app:app", \
     "--host", "0.0.0.0", "--port", "8080"]
