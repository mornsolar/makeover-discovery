"""``JinjaLandingPageBuilder``, writing a real page to a real directory."""

from __future__ import annotations

from datetime import UTC, datetime

from makeover_contracts.jobs import ArtifactBundle, ArtifactKind, ArtifactRef, JobStatus, RenderJob

from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource, Project
from makeover_discovery.infrastructure.landing.jinja_landing_builder import (
    AI_DISCLOSURE_TEXT,
    JinjaLandingPageBuilder,
)
from tests.fakes.brief import make_profile
from tests.fakes.specs import make_scene_spec

SUBMITTED_AT = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)


def _ref(kind: ArtifactKind, path) -> ArtifactRef:
    return ArtifactRef(
        kind=kind,
        uri=str(path),
        media_type="application/octet-stream",
        size_bytes=1,
        sha256="a" * 64,
    )


def _rendered_project(tmp_path, *, published: bool = False, takedown: bool = False) -> Project:
    tmp_path.mkdir(parents=True, exist_ok=True)
    video = tmp_path / "animation.mp4"
    gltf = tmp_path / "scene.glb"
    thumb = tmp_path / "thumbnail.png"
    for path in (video, gltf, thumb):
        path.write_bytes(b"x")

    business = make_profile()
    spec = make_scene_spec()
    bundle = ArtifactBundle(
        gltf=_ref(ArtifactKind.GLTF, gltf),
        video=_ref(ArtifactKind.VIDEO, video),
        thumbnail=_ref(ArtifactKind.THUMBNAIL, thumb),
    )
    job = RenderJob(
        id="job-1",
        spec=spec,
        status=JobStatus.SUCCEEDED,
        created_at=SUBMITTED_AT,
        finished_at=SUBMITTED_AT,
        artifacts=bundle,
    )
    pipeline = PipelineResult(
        business=business,
        outcome=PipelineOutcome.RENDERED,
        scene_spec=spec,
        render_job=job,
    )
    return Project(
        id=business.id,
        pipeline=pipeline,
        before_image=BeforeImage(
            uri="https://example.com/before.jpg", source=BeforeImageSource.AUTO_PHOTO
        ),
        created_at=SUBMITTED_AT,
        published=published,
        takedown=takedown,
    )


async def test_a_draft_page_carries_the_watermark(tmp_path):
    project = _rendered_project(tmp_path / "src", published=False)
    out_dir = tmp_path / "out"

    index_path = await JinjaLandingPageBuilder().build(project, out_dir)

    html = index_path.read_text(encoding="utf-8")
    assert "DRAFT" in html
    assert AI_DISCLOSURE_TEXT in html


async def test_a_published_page_has_no_watermark(tmp_path):
    project = _rendered_project(tmp_path / "src", published=True)
    out_dir = tmp_path / "out"

    index_path = await JinjaLandingPageBuilder().build(project, out_dir)

    assert "DRAFT" not in index_path.read_text(encoding="utf-8")


async def test_copies_video_gltf_and_thumbnail_into_assets(tmp_path):
    project = _rendered_project(tmp_path / "src", published=True)
    out_dir = tmp_path / "out"

    await JinjaLandingPageBuilder().build(project, out_dir)

    assert (out_dir / "assets" / "animation.mp4").exists()
    assert (out_dir / "assets" / "scene.glb").exists()
    assert (out_dir / "assets" / "thumbnail.png").exists()
    assert (out_dir / "assets" / "model-viewer.min.js").exists()


async def test_a_remote_before_image_is_referenced_not_downloaded(tmp_path):
    project = _rendered_project(tmp_path / "src", published=True)
    out_dir = tmp_path / "out"

    index_path = await JinjaLandingPageBuilder().build(project, out_dir)

    assert "https://example.com/before.jpg" in index_path.read_text(encoding="utf-8")
    assert not (out_dir / "assets" / "before.jpg").exists()


async def test_a_takedown_project_gets_a_placeholder_page_instead(tmp_path):
    project = _rendered_project(tmp_path / "src", published=True, takedown=True)
    out_dir = tmp_path / "out"

    index_path = await JinjaLandingPageBuilder().build(project, out_dir)

    html = index_path.read_text(encoding="utf-8")
    assert "removed" in html.lower()
    assert AI_DISCLOSURE_TEXT not in html
