# makeover-contracts

The versioned wire contract shared by **makeover-discovery** (Repo A) and
**makeover-render** (Repo B).

Pydantic v2 models only. No I/O, no framework, no dependency beyond pydantic —
either repository can adopt a new version without inheriting the other's stack.

## Why it lives here

It is published from Repo A but owned by neither. Repo B installs it by pinned
git tag:

```
makeover-contracts @ git+https://.../makeover-discovery@contracts-v0.1.0#subdirectory=packages/makeover-contracts
```

If shared ownership becomes friction, it graduates to its own repository. Not yet.

## The dependency rule

Repo B never imports Repo A. Instead it publishes a `CapabilityManifest`
describing what it can render; Repo A reads that manifest, constrains the LLM to
its vocabulary, and calls `validate_against_manifest()` before submitting a
`SceneSpec`. Both sides share one implementation of "would this render?".

## Provenance is structural

`Provenanced[T]` binds a value to the `SourceRef` that supplied it. A
third-party field cannot exist in a `BusinessProfile` without recording where it
came from, under what licence, and when it must be purged — enforced by the type
rather than by convention.

## Schemas

`schemas/*.json` are generated and checked in, so the contract is readable
without Python and CI can detect drift.

```bash
uv run makeover-contracts-export           # regenerate
uv run makeover-contracts-export --check   # CI drift gate
```

## Versioning

`CONTRACT_VERSION` follows semver. Additive minor/patch changes are backward
compatible; `is_compatible()` compares major versions only.
