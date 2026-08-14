# makeover-discovery

Postcode → local businesses → permitted public info → LLM design brief →
orchestration → before/after landing page.

Repo A of two. The Blender side lives in **makeover-render**, which this service
drives over HTTP. Neither repo imports the other; they share only the versioned
`makeover-contracts` package in `packages/`.

## Status

**Phase 6a complete — pipeline core.** The two repos talk to each other for
real now: `makeover pipeline <postcode>` discovers a business, enriches it,
generates a design brief, deterministically composes a `SceneSpec` from it
(`ComposeSceneSpec` — template pick, material/colour assignment, signage
truncation, all derived from the business's own identity so the result is
stable across runs), submits it to `makeover-render`'s `POST /jobs`, and
polls `GET /jobs/{id}` until the render finishes. `RunMakeoverPipeline`
processes a batch of businesses and isolates failures per business — one
business's brief or render failure does not discard the others' results.

**Live-verified end to end**, not just green tests: with a real `redis-server`
+ `arq` worker + `uvicorn` running `makeover-render`, `makeover pipeline 50450
--country MY --limit 1` discovered a real business from OpenStreetMap,
generated a **real** design brief via the live Anthropic API (this machine's
`.env` has a key configured, so this also closed Phase 3's previously-open
"not verified against live Anthropic" gap), composed a valid `SceneSpec`,
and got back a real rendered `.mp4`/`.glb`/thumbnail — `ffprobe` confirmed a
genuine 960×540/12fps/36-frame H.264 stream matching `ComposeSceneSpec`'s own
render settings exactly. The config guard was checked too: with
`MAKEOVER_RENDER_SERVICE_URL` unset, the command fails fast with a clear
`not configured` message rather than a confusing failure deeper in the
pipeline.

**Not yet built (Phase 6b): persistence, the landing page, and the publish
gate.** Nothing from this pipeline run is saved anywhere — `PipelineResult`
lives only in memory for the duration of one CLI invocation. There is no
`Project` aggregate, no database, no before/after landing page, and no
`makeover run ... --out ./site` command yet; see the roadmap plan for the
6b scope (SQLAlchemy/Alembic storage, local artifact store, Jinja2 landing
page with a self-hosted `<model-viewer>`, private-by-default publish gate,
manual before-image upload).

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

Discover, then pull permitted public info from each business's own site:

```bash
uv run makeover enrich 50450 --country MY --limit 4
```

Then infer art direction for it (needs `MAKEOVER_ANTHROPIC_API_KEY`; each brief
is a paid model call, so the default limit is one):

```bash
uv run makeover brief 50450 --country MY --limit 1
```

Run the full pipeline through to a real render (needs `MAKEOVER_RENDER_SERVICE_URL`
pointing at a running `makeover-render`, plus everything `brief` needs — this
is also a paid model call, so the default limit is one):

```bash
uv run makeover pipeline 50450 --country MY --limit 1
```

```bash
curl -s localhost:8080/discover -H 'content-type: application/json' \
  -d '{"postcode": "50450", "country": "MY", "limit": 8, "categories": ["cafe"]}'
```

Set `MAKEOVER_USER_AGENT` to something that identifies you and gives a contact
address before pointing this at public OpenStreetMap services — the service
refuses to start in `production` without it.

**Playwright fallback** (optional, off by default): `uv sync` installs the
`playwright` Python package but not a browser. To enable it:

```bash
uv run playwright install chromium
```

then set `MAKEOVER_USE_PLAYWRIGHT_FALLBACK=true`. The plain HTTP fetcher runs
first for every page; Playwright only launches when the result looks like an
unrendered JS shell (measured live: a page with almost no visible text once
scripts and style are stripped out).

**Google Places** (optional, off by default): set
`MAKEOVER_GOOGLE_PLACES_ENABLED=true` and `MAKEOVER_GOOGLE_PLACES_API_KEY`.
When enabled it replaces Overpass as the directory for `/discover`; OpenStreetMap
stays the default because it needs no key. The service refuses to start with
the flag on and no key configured.

**Design briefs** need `MAKEOVER_ANTHROPIC_API_KEY`. Everything else runs
without it; the brief use case refuses to build rather than failing partway
through a pipeline, and `production` refuses to start without it. Defaults:
`claude-opus-5` at `high` effort, one repair round.

The renderer's vocabulary — material families, camera moves, lighting rigs —
comes from `makeover-render`'s `GET /capabilities` when
`MAKEOVER_RENDER_SERVICE_URL` is set, and otherwise from a manifest compiled
into this build. The model can only choose from that vocabulary: it is encoded
as enums in the forced tool schema and re-checked afterwards, with any problems
fed back in a single repair round. Three exclusions — real logos, invented
factual claims, and signage naming a person — are written into every brief by
this service rather than requested from the model.

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
sits behind the same `BusinessDirectory` port. Nominatim's usage policy
requires an identifying User-Agent and roughly 1 request/second, so rate
limiting and caching are requirements, not optimisations.

Google Places candidates are built through the same `RetentionPolicy` that
gives OpenStreetMap data no expiry — Places gets its 30-day caching limit
stamped onto every `SourceRef` for free, decided once rather than reimplemented
per adapter. Places' own hard limits are honoured explicitly: `maxResultCount`
is capped at 20 (a real API ceiling, not a choice), and the field mask is
scoped to exactly what `BusinessCandidate` uses, since Places bills per field
requested.

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
