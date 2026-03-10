from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Sample:
    sample_id: str
    scenario: str
    case_id: str
    pair_mode: str
    left_label: str
    right_label: str
    reference_video_relative: str
    generated_video_relative: str
    action_path_relative: str
    preview_image_relative: str | None
    reference_video: Path
    generated_video: Path
    action_path: Path
    preview_image: Path | None
    reference_video_meta: dict[str, Any]
    generated_video_meta: dict[str, Any]
    action_summary: dict[str, Any]
    action_markdown: str


@dataclass(frozen=True)
class DatasetManifest:
    manifest_path: Path
    dataset_root: Path
    pair_mode: str
    sample_count: int
    scenario_summaries: list[dict[str, Any]]
    warnings: list[str]
    samples: list[Sample]


def ensure_manifest(manifest_path: Path | None = None, rebuild: bool = False) -> Path:
    manifest_path = manifest_path or default_manifest_path()
    if rebuild or not manifest_path.exists():
        build_manifest_module = _import_build_manifest()
        build_manifest_module.write_manifest(
            dataset_root=default_dataset_root(),
            manifest_path=manifest_path,
            repo_root=repo_root(),
        )
    return manifest_path


def load_manifest(manifest_path: Path | None = None) -> DatasetManifest:
    manifest_path = manifest_path or default_manifest_path()
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    root = repo_root()
    samples = [
        Sample(
            sample_id=item["sample_id"],
            scenario=item["scenario"],
            case_id=item["case_id"],
            pair_mode=item.get("pair_mode", "reference_vs_wangame"),
            left_label=item.get("left_label", "Left"),
            right_label=item.get("right_label", "Right"),
            reference_video_relative=item["reference_video"],
            generated_video_relative=item["generated_video"],
            action_path_relative=item["action_path"],
            preview_image_relative=item.get("preview_image"),
            reference_video=_resolve_repo_path(root, item["reference_video"]),
            generated_video=_resolve_repo_path(root, item["generated_video"]),
            action_path=_resolve_repo_path(root, item["action_path"]),
            preview_image=_resolve_repo_path(root, item["preview_image"]) if item.get("preview_image") else None,
            reference_video_meta=item.get("reference_video_meta", {}),
            generated_video_meta=item.get("generated_video_meta", {}),
            action_summary=item.get("action_summary", {}),
            action_markdown=item.get("action_markdown", "Action summary unavailable."),
        )
        for item in payload.get("samples", [])
    ]

    dataset_root_value = payload.get("dataset_root")
    dataset_root = _resolve_repo_path(root, dataset_root_value) if dataset_root_value else default_dataset_root()

    return DatasetManifest(
        manifest_path=manifest_path,
        dataset_root=dataset_root,
        pair_mode=payload.get("pair_mode", "reference_vs_wangame"),
        sample_count=int(payload.get("sample_count", len(samples))),
        scenario_summaries=list(payload.get("scenario_summaries", [])),
        warnings=list(payload.get("warnings", [])),
        samples=samples,
    )


def default_manifest_path() -> Path:
    return repo_root() / "arena" / "manifest.json"


def default_dataset_root() -> Path:
    return repo_root() / "data_subset"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_repo_path(root: Path, value: str | None) -> Path:
    if not value:
        return root
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _import_build_manifest():
    try:
        from . import build_manifest as build_manifest_module
    except ImportError:
        import build_manifest as build_manifest_module

    return build_manifest_module
