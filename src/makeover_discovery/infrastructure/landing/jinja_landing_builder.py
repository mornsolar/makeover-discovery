"""Jinja2-backed ``LandingPageBuilder``.

Copies every local asset a project needs (video, glb, thumbnail, before-image
when it isn't already a remote URL, the vendored ``<model-viewer>`` bundle)
into ``out_dir/assets/`` and writes a self-contained ``index.html`` - the
whole directory is meant to be portable to a static host later, not just
readable from where it was generated.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

from makeover_discovery.domain.model.project import Project

_PACKAGE_DIR: Final = Path(__file__).parent
_TEMPLATES_DIR: Final = _PACKAGE_DIR / "templates"
_STATIC_DIR: Final = _PACKAGE_DIR / "static"
_MODEL_VIEWER_FILENAME: Final = "model-viewer.min.js"

AI_DISCLOSURE_TEXT: Final = (
    "AI-generated concept — not affiliated with this business, not an architectural proposal."
)


class JinjaLandingPageBuilder:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=select_autoescape(["html"]),
        )

    async def build(self, project: Project, out_dir: Path) -> Path:
        assets_dir = out_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_STATIC_DIR / _MODEL_VIEWER_FILENAME, assets_dir / _MODEL_VIEWER_FILENAME)

        if project.takedown:
            # The roadmap's "hard-disables" language means the artifacts must
            # not still be reachable through the normal page once taken down.
            html = self._env.get_template("takedown.html.jinja").render(
                business_name=project.pipeline.business.name.value,
            )
        else:
            html = self._env.get_template("project.html.jinja").render(
                **self._context(project, assets_dir)
            )

        index_path = out_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")
        return index_path

    def _context(self, project: Project, assets_dir: Path) -> dict[str, object]:
        business = project.pipeline.business
        before_image_src = None
        if project.before_image is not None:
            suffix = Path(project.before_image.uri).suffix or ".jpg"
            before_image_src = _copy_or_pass_through(
                project.before_image.uri, assets_dir, f"before{suffix}"
            )

        artifacts = project.pipeline.render_job.artifacts if project.pipeline.render_job else None
        video_src = gltf_src = thumbnail_src = None
        if artifacts is not None:
            video_src = _copy_or_pass_through(artifacts.video.uri, assets_dir, "animation.mp4")
            gltf_src = _copy_or_pass_through(artifacts.gltf.uri, assets_dir, "scene.glb")
            thumbnail_src = _copy_or_pass_through(
                artifacts.thumbnail.uri, assets_dir, "thumbnail.png"
            )

        return {
            "project": project,
            "business_name": business.name.value,
            "business_category": business.category.value,
            "attributions": business.attributions(),
            "before_image_src": before_image_src,
            "video_src": video_src,
            "gltf_src": gltf_src,
            "thumbnail_src": thumbnail_src,
            "model_viewer_src": f"assets/{_MODEL_VIEWER_FILENAME}",
            "disclosure_text": AI_DISCLOSURE_TEXT,
        }


def _copy_or_pass_through(uri: str, assets_dir: Path, filename: str) -> str:
    """A local file is copied into ``assets_dir``; a remote URL is passed
    through unchanged - a browser can load it directly, and fetching an
    arbitrary third-party URL here would be an unprompted network call this
    use case has no business making."""
    if uri.startswith(("http://", "https://")):
        return uri
    shutil.copyfile(Path(uri), assets_dir / filename)
    return f"assets/{filename}"
