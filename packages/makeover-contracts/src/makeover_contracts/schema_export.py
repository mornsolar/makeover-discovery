"""Export the contract as JSON Schema documents.

The generated files are checked into ``schemas/`` so the contract is readable
without a Python toolchain, and so CI can fail when a model changes without a
corresponding regeneration. ``--check`` is the CI mode: it regenerates into a
temporary buffer and diffs, changing nothing on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessCandidate, BusinessProfile
from makeover_contracts.capability import CapabilityManifest
from makeover_contracts.jobs import ArtifactBundle, RenderJob
from makeover_contracts.scene import SceneSpec
from makeover_contracts.version import CONTRACT_VERSION

DEFAULT_OUTPUT_DIR: Final = Path(__file__).resolve().parents[2] / "schemas"

EXPORTED_MODELS: Final[dict[str, type[BaseModel]]] = {
    "business_candidate": BusinessCandidate,
    "business_profile": BusinessProfile,
    "design_brief": DesignBrief,
    "scene_spec": SceneSpec,
    "capability_manifest": CapabilityManifest,
    "render_job": RenderJob,
    "artifact_bundle": ArtifactBundle,
}


def render_schema(model: type[BaseModel]) -> str:
    """Serialize one model's JSON Schema deterministically.

    Keys are sorted and the trailing newline is explicit so the output is stable
    across runs and diffs cleanly.
    """
    schema = model.model_json_schema()
    schema["$comment"] = f"makeover-contracts {CONTRACT_VERSION}"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def export(output_dir: Path) -> list[Path]:
    """Write every exported model's schema, returning the paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in EXPORTED_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(render_schema(model), encoding="utf-8")
        written.append(path)
    return written


def find_drift(output_dir: Path) -> list[str]:
    """Return names whose on-disk schema differs from the current models."""
    drifted: list[str] = []
    for name, model in EXPORTED_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        if not path.exists():
            drifted.append(f"{name} (missing)")
            continue
        if path.read_text(encoding="utf-8") != render_schema(model):
            drifted.append(f"{name} (stale)")
    return drifted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export makeover contract JSON Schemas.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in schemas are out of date; write nothing.",
    )
    args = parser.parse_args(argv)

    if args.check:
        drifted = find_drift(args.output)
        if drifted:
            print("Schemas are out of date: " + ", ".join(drifted), file=sys.stderr)
            print("Regenerate with: makeover-contracts-export", file=sys.stderr)
            return 1
        print(f"{len(EXPORTED_MODELS)} schemas up to date.")
        return 0

    written = export(args.output)
    print(f"Wrote {len(written)} schemas to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
