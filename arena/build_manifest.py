from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from .actions import build_action_summary, summary_to_manifest_dict
except ImportError:
    from actions import build_action_summary, summary_to_manifest_dict


GENERATED_SUFFIX = "_wangame.mp4"
ACTION_SUFFIX = "_action.npy"


def build_manifest(dataset_root: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    dataset_root = dataset_root.resolve()

    samples: list[dict[str, Any]] = []
    warnings: list[str] = []
    scenario_summaries: list[dict[str, Any]] = []

    for scenario_dir in sorted(path for path in dataset_root.iterdir() if path.is_dir()):
        indexed_cases = _index_scenario_cases(scenario_dir)
        valid_case_ids: list[str] = []

        for case_id in sorted(indexed_cases):
            entry = indexed_cases[case_id]
            missing = [
                field
                for field in ("reference_video", "generated_video", "action_path")
                if field not in entry
            ]
            if missing:
                warnings.append(
                    f"Skipping {scenario_dir.name}/{case_id}: missing {', '.join(sorted(missing))}"
                )
                continue

            reference_video = entry["reference_video"]
            generated_video = entry["generated_video"]
            action_path = entry["action_path"]
            preview_image = entry.get("preview_image")

            reference_meta = probe_video(reference_video)
            generated_meta = probe_video(generated_video)
            fps = (
                generated_meta.get("fps")
                or reference_meta.get("fps")
                or generated_meta.get("avg_frame_rate")
                or reference_meta.get("avg_frame_rate")
            )
            action_summary = build_action_summary(action_path, fps=fps)

            sample = {
                "sample_id": f"{scenario_dir.name}/{case_id}",
                "scenario": scenario_dir.name,
                "case_id": case_id,
                "pair_mode": "reference_vs_wangame",
                "left_label": "Reference (.mp4)",
                "right_label": "Generated (WanGame)",
                "reference_video": _path_for_manifest(reference_video, repo_root),
                "generated_video": _path_for_manifest(generated_video, repo_root),
                "preview_image": _path_for_manifest(preview_image, repo_root) if preview_image else None,
                "action_path": _path_for_manifest(action_path, repo_root),
                "reference_video_meta": reference_meta,
                "generated_video_meta": generated_meta,
                "action_summary": summary_to_manifest_dict(action_summary),
                "action_markdown": action_summary.markdown,
            }
            samples.append(sample)
            valid_case_ids.append(case_id)

        scenario_summaries.append(
            {
                "scenario": scenario_dir.name,
                "n_samples": len(valid_case_ids),
                "case_ids": valid_case_ids,
            }
        )

    return {
        "manifest_version": 1,
        "created_at": _utc_now(),
        "repo_root": _path_for_manifest(repo_root.resolve(), repo_root),
        "dataset_root": _path_for_manifest(dataset_root, repo_root),
        "pair_mode": "reference_vs_wangame",
        "sample_count": len(samples),
        "scenario_summaries": scenario_summaries,
        "samples": samples,
        "warnings": warnings,
    }


def write_manifest(dataset_root: Path, manifest_path: Path, repo_root: Path | None = None) -> Path:
    manifest = build_manifest(dataset_root=dataset_root, repo_root=repo_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest_path


def probe_video(video_path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,nb_frames,duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {}
    except subprocess.CalledProcessError:
        return {}

    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
    except (json.JSONDecodeError, KeyError, IndexError):
        return {}

    fps_text = stream.get("avg_frame_rate")
    fps = _parse_fraction(fps_text)
    duration = _parse_float(stream.get("duration"))
    nb_frames = _parse_int(stream.get("nb_frames"))

    return {
        "width": _parse_int(stream.get("width")),
        "height": _parse_int(stream.get("height")),
        "avg_frame_rate": fps,
        "fps": fps,
        "duration_s": duration,
        "nb_frames": nb_frames,
    }


def _index_scenario_cases(scenario_dir: Path) -> dict[str, dict[str, Path]]:
    indexed: dict[str, dict[str, Path]] = {}
    for path in sorted(candidate for candidate in scenario_dir.iterdir() if candidate.is_file()):
        case_id: str | None = None
        field: str | None = None
        if path.name.endswith(ACTION_SUFFIX):
            case_id = path.name[: -len(ACTION_SUFFIX)]
            field = "action_path"
        elif path.name.endswith(GENERATED_SUFFIX):
            case_id = path.name[: -len(GENERATED_SUFFIX)]
            field = "generated_video"
        elif path.suffix.lower() == ".mp4":
            case_id = path.stem
            field = "reference_video"
        elif path.suffix.lower() == ".jpg":
            case_id = path.stem
            field = "preview_image"

        if case_id and field:
            indexed.setdefault(case_id, {})[field] = path.resolve()
    return indexed


def _path_for_manifest(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _parse_fraction(value: Any) -> float | None:
    if not value:
        return None
    try:
        return float(Fraction(str(value)))
    except (ZeroDivisionError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    repo_root = _default_repo_root()
    parser = argparse.ArgumentParser(description="Build a normalized dataset manifest for arena.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=repo_root / "data_subset",
        help="Path to the dataset root (default: repo_root/data_subset)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repo_root / "arena" / "manifest.json",
        help="Path to the manifest JSON file to write",
    )
    args = parser.parse_args()

    manifest_path = write_manifest(
        dataset_root=args.dataset_root,
        manifest_path=args.manifest,
        repo_root=repo_root,
    )
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
