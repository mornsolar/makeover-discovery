# makeover-discovery

Postcode → local businesses → permitted public info → LLM design brief →
orchestration → before/after landing page.

Repo A of two. The Blender side lives in **makeover-render**, which this service
drives over HTTP. Neither repo imports the other; they share only the versioned
`makeover-contracts` package in `packages/`.

## Status

**Phase 0 — foundations.** Contracts v0.1, toolchain, CI, and `/health` are in
place. Discovery, enrichment, and brief generation arrive in Phases 1–3.

## Quickstart

```bash
make install     # uv sync --all-packages
make check       # lint + strict types + schema drift + tests
make run         # serve on :8080
```

```bash
curl -s localhost:8080/health
```

## Architecture

Clean architecture, dependencies pointing inward:

| Layer | Rule |
|---|---|
| `domain/` | Pure. No I/O, no framework imports, no third-party SDKs |
| `application/` | Use cases and **ports** (`typing.Protocol`) |
| `infrastructure/` | One adapter per port — Nominatim, Overpass, Playwright, Anthropic, storage |
| `interfaces/` | FastAPI routers, worker tasks, CLI |

`interfaces/api/deps.py` is the **composition root** — the only module naming
concrete adapters. Ports are Protocols, so tests inject fakes rather than mocks.
There is no DI framework: `Depends` plus structural typing already gives
constructor injection and request scoping.

## Data sources and compliance

OpenStreetMap (Nominatim + Overpass) is primary; Google Places is optional and
sits behind the same port. Nominatim's usage policy requires an identifying
User-Agent and roughly 1 request/second, so rate limiting and caching are
requirements, not optimisations.

Every third-party field is wrapped in `Provenanced[T]` and cannot exist without
a `SourceRef` recording source, licence, fetch time, and retention deadline.
Attribution rendering and the retention sweeper both derive from that.

## A standing constraint

This system generates makeover visualizations of **real businesses that have not
consented**. Landing pages are private by default, carry an explicit
AI-generated / not-affiliated disclosure, never reproduce logos or brand marks,
and support a takedown flag. Treat these as functional requirements.

## Testing

```bash
uv run pytest
```

Coverage gate is 80%. No test performs a live network or LLM call.
