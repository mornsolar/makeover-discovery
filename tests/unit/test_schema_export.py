from __future__ import annotations

import json

from makeover_contracts.scene import SceneSpec
from makeover_contracts.schema_export import (
    EXPORTED_MODELS,
    export,
    find_drift,
    main,
    render_schema,
)


class TestRenderSchema:
    def test_is_deterministic_across_calls(self):
        # Golden-file drift detection depends on byte-for-byte stability.
        assert render_schema(SceneSpec) == render_schema(SceneSpec)

    def test_stamps_the_contract_version(self):
        schema = json.loads(render_schema(SceneSpec))
        assert schema["$comment"] == "makeover-contracts 0.1.0"

    def test_ends_with_a_newline(self):
        assert render_schema(SceneSpec).endswith("\n")


class TestExport:
    def test_writes_one_file_per_exported_model(self, tmp_path):
        written = export(tmp_path)
        assert len(written) == len(EXPORTED_MODELS)
        assert (tmp_path / "scene_spec.schema.json").exists()

    def test_creates_the_output_directory(self, tmp_path):
        target = tmp_path / "nested" / "schemas"
        export(target)
        assert target.is_dir()


class TestFindDrift:
    def test_reports_nothing_immediately_after_an_export(self, tmp_path):
        export(tmp_path)
        assert find_drift(tmp_path) == []

    def test_reports_missing_schemas(self, tmp_path):
        assert len(find_drift(tmp_path)) == len(EXPORTED_MODELS)

    def test_reports_a_stale_schema(self, tmp_path):
        export(tmp_path)
        (tmp_path / "scene_spec.schema.json").write_text("{}", encoding="utf-8")
        assert find_drift(tmp_path) == ["scene_spec (stale)"]


class TestMain:
    def test_check_succeeds_when_schemas_are_current(self, tmp_path):
        export(tmp_path)
        assert main(["--output", str(tmp_path), "--check"]) == 0

    def test_check_fails_when_schemas_are_missing(self, tmp_path):
        assert main(["--output", str(tmp_path), "--check"]) == 1

    def test_write_mode_produces_schemas(self, tmp_path):
        assert main(["--output", str(tmp_path)]) == 0
        assert (tmp_path / "design_brief.schema.json").exists()
