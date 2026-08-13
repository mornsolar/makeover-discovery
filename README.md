# makeover-discovery

Postcode → local businesses → permitted public info → LLM design brief →
orchestration → before/after landing page.

Repo A of two. The Blender side lives in **makeover-render**, which this service
drives over HTTP. Neither repo imports the other; they share only the versioned
`makeover-contracts` package in `packages/`.

## Status

**Phase 1 — discovery core.** `Postcode → GeoArea → BusinessCandidate[]` works
end to end against live OpenStreetMap, via `POST /discover` and the
`makeover discover` CLI. Enrichment and brief generation arrive in Phases 2–3.

## Quickstart

```bash
make install     # uv sync --all-packages
make check       # lint + strict types + schema drift + tests
make run         # serve on :8080
```

```bash
curl -s localhost:8080/health
```

Find businesses near a postcode:

```bash
uv run makeover discover 50450 --country MY --limit 8
```

```bash
curl -s localhost:8080/discover -H 'content-type: application/json' \
  -d '{"postcode": "50450", "country": "MY", "limit": 8, "categories": ["cafe"]}'
```

Set `MAKEOVER_USER_AGENT` to something that identifies you and gives a contact
address before pointing this at public OpenStreetMap services — the service
refuses to start in `production` without it.

## Architecture

Clean architecture, dependencies pointing inward:

| Layer | Rule |
|---|---|
| `domain/` | Pure. No I/O, no framework imports, no third-party SDKs |
| `application/` | Use cases and **ports** (`typing.Protocol`) |
| `infrastructure/` | One adapter per port — Nominatim, Overpass, Playwright, Anthropic, storage |
| `interfaces/` | FastAPI routers, worker tasks, CLI |

`composition.py` builds the object graph and is the only module naming
concrete adapters; `interfaces/api/deps.py` exposes it as FastAPI dependencies
and the CLI calls it directly, so both interfaces exercise identical wiring. Ports are Protocols, so tests inject fakes rather than mocks.
There is no DI framework: `Depends` plus structural typing already gives
constructor injection and request scoping.

## Data sources and compliance

OpenStreetMap (Nominatim + Overpass) is primary; Google Places is optional and
sits behind the same port. Nominatim's usage policy requires an identifying
User-Agent and roughly 1 request/second, so rate limiting and caching are
requirements, not optimisations.

Two behaviours here were forced by live data rather than by the docs, and both
are load-bearing:

- **A geocoded bounding box is capped** (`max_search_radius_m`). Nominatim
  synthesises a padded box around a postcode *point* — measured at 7 km for
  50450 — which otherwise drags in whole neighbouring postcodes.
- **The Overpass query carries no element limit.** Overpass cannot sort by
  distance, so its `out` limit truncates by quadtile: a 500-element cap
  returned nothing closer than 1.2 km when the true nearest business was 77 m
  away. The whole area is fetched and ranked locally instead, which is why the
  radius cap doubles as the response-size bound.

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
