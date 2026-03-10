from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gradio as gr

try:
    from .dataset import DatasetManifest, Sample, ensure_manifest, load_manifest
    from .result_logger import append_annotation
except ImportError:
    from dataset import DatasetManifest, Sample, ensure_manifest, load_manifest
    from result_logger import append_annotation


VOTE_CHOICES = ["Left better", "Tie / unsure", "Right better"]
FLAG_HELP = (
    "No artifact flags recorded yet. Pause a player, read the native timestamp, "
    "type it below, and click `Flag artifact`."
)


def build_app(
    manifest: DatasetManifest,
    results_dir: Path,
    writes_enabled: bool = True,
) -> gr.Blocks:
    if not manifest.samples:
        raise ValueError("Manifest contains no samples.")

    first_sample = manifest.samples[0]
    first_title = _sample_title(first_sample, 0, len(manifest.samples))
    first_metadata = _sample_metadata(first_sample)
    first_status = _status_message(
        f"Loaded `{first_sample.sample_id}`. Save an annotation, then move to the next sample."
    )

    with gr.Blocks(title="Minecraft LM-Arena Baseline") as demo:
        current_index = gr.State(0)
        artifact_flags = gr.State([])

        gr.Markdown("# Minecraft LM-Arena Baseline")
        gr.Markdown(
            "Left is the reference `.mp4`; right is the paired WanGame `_wangame.mp4` output. "
            "Players are independent. The artifact button uses a manual timestamp fallback because "
            "plain Gradio does not reliably expose live `currentTime` from both video widgets."
        )
        if not writes_enabled:
            gr.Markdown(
                "**Read-only mode:** annotation writes are disabled. "
                "Use this for public demo review until the final eval schema is settled."
            )

        sample_title = gr.Markdown(first_title)
        sample_metadata = gr.Markdown(first_metadata)

        with gr.Row():
            left_video = gr.Video(
                value=str(first_sample.reference_video),
                label=first_sample.left_label,
            )
            right_video = gr.Video(
                value=str(first_sample.generated_video),
                label=first_sample.right_label,
            )

        action_markdown = gr.Markdown(first_sample.action_markdown)

        with gr.Row():
            action_following = gr.Radio(
                choices=VOTE_CHOICES,
                label="Action following",
            )
            visual_quality = gr.Radio(
                choices=VOTE_CHOICES,
                label="Visual quality",
            )
            temporal_consistency = gr.Radio(
                choices=VOTE_CHOICES,
                label="Temporal consistency",
            )

        tie_all = gr.Button("Tie all / unsure")
        tie_all.click(
            fn=lambda: ("Tie / unsure", "Tie / unsure", "Tie / unsure"),
            outputs=[action_following, visual_quality, temporal_consistency],
        )

        gr.Markdown(
            "Artifact flagging fallback: enter the paused player time in seconds, then record it."
        )
        with gr.Row():
            artifact_time_input = gr.Textbox(
                label="Artifact timestamp (seconds)",
                placeholder="Example: 1.24",
            )
            flag_artifact = gr.Button("Flag artifact")
            clear_artifacts = gr.Button("Clear artifact flags")

        artifact_markdown = gr.Markdown(FLAG_HELP)
        note = gr.Textbox(lines=3, label="Optional note")

        with gr.Row():
            save_button = gr.Button(
                "Save annotation",
                variant="primary",
                interactive=writes_enabled,
            )
            prev_button = gr.Button("Previous sample")
            next_button = gr.Button("Next sample")

        status = gr.Markdown(first_status)

        flag_artifact.click(
            fn=record_artifact_flag,
            inputs=[artifact_time_input, artifact_flags],
            outputs=[artifact_flags, artifact_markdown, artifact_time_input, status],
        )
        clear_artifacts.click(
            fn=lambda: ([], FLAG_HELP, "", _status_message("Cleared artifact flags.")),
            outputs=[artifact_flags, artifact_markdown, artifact_time_input, status],
        )
        save_button.click(
            fn=lambda index, flags, action_vote, visual_vote, temporal_vote, note_text: save_annotation(
                manifest=manifest,
                results_dir=results_dir,
                sample_index=index,
                flags=flags,
                action_vote=action_vote,
                visual_vote=visual_vote,
                temporal_vote=temporal_vote,
                note_text=note_text,
                writes_enabled=writes_enabled,
            ),
            inputs=[
                current_index,
                artifact_flags,
                action_following,
                visual_quality,
                temporal_consistency,
                note,
            ],
            outputs=[status],
        )
        prev_button.click(
            fn=lambda index: navigate_sample(manifest, index - 1),
            inputs=[current_index],
            outputs=_sample_outputs(
                sample_title,
                sample_metadata,
                left_video,
                right_video,
                action_markdown,
                action_following,
                visual_quality,
                temporal_consistency,
                artifact_time_input,
                artifact_markdown,
                note,
                status,
                current_index,
                artifact_flags,
            ),
        )
        next_button.click(
            fn=lambda index: navigate_sample(manifest, index + 1),
            inputs=[current_index],
            outputs=_sample_outputs(
                sample_title,
                sample_metadata,
                left_video,
                right_video,
                action_markdown,
                action_following,
                visual_quality,
                temporal_consistency,
                artifact_time_input,
                artifact_markdown,
                note,
                status,
                current_index,
                artifact_flags,
            ),
        )

    return demo


def navigate_sample(manifest: DatasetManifest, requested_index: int) -> tuple[Any, ...]:
    sample_count = len(manifest.samples)
    sample_index = max(0, min(requested_index, sample_count - 1))
    sample = manifest.samples[sample_index]
    status = _status_message(f"Loaded `{sample.sample_id}`.")
    return (
        _sample_title(sample, sample_index, sample_count),
        _sample_metadata(sample),
        str(sample.reference_video),
        str(sample.generated_video),
        sample.action_markdown,
        None,
        None,
        None,
        "",
        FLAG_HELP,
        "",
        status,
        sample_index,
        [],
    )


def record_artifact_flag(
    artifact_time_text: str,
    existing_flags: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], str, str, str]:
    existing_flags = list(existing_flags or [])
    try:
        timestamp_s = round(float(artifact_time_text.strip()), 3)
    except (AttributeError, ValueError):
        return (
            existing_flags,
            _artifact_markdown(existing_flags),
            artifact_time_text,
            _status_message("Enter a numeric timestamp before flagging an artifact."),
        )

    if timestamp_s < 0:
        return (
            existing_flags,
            _artifact_markdown(existing_flags),
            artifact_time_text,
            _status_message("Artifact timestamps must be zero or positive."),
        )

    existing_flags.append(
        {
            "timestamp_s": timestamp_s,
            "source": "manual_text_entry",
            "recorded_at": _utc_now(),
        }
    )
    return (
        existing_flags,
        _artifact_markdown(existing_flags),
        "",
        _status_message(f"Flagged artifact at {timestamp_s:.3f}s."),
    )


def save_annotation(
    manifest: DatasetManifest,
    results_dir: Path,
    sample_index: int,
    flags: list[dict[str, Any]] | None,
    action_vote: str | None,
    visual_vote: str | None,
    temporal_vote: str | None,
    note_text: str,
    writes_enabled: bool,
) -> str:
    if not writes_enabled:
        return _status_message(
            "Annotation writes are disabled in this deployment. "
            "Set `ARENA_DISABLE_WRITES=0` or omit `--disable-writes` to enable saving."
        )

    missing = [
        label
        for label, value in (
            ("action following", action_vote),
            ("visual quality", visual_vote),
            ("temporal consistency", temporal_vote),
        )
        if not value
    ]
    if missing:
        return _status_message(f"Select votes for: {', '.join(missing)}.")

    sample = manifest.samples[sample_index]
    flags = list(flags or [])
    record = {
        "annotated_at": _utc_now(),
        "sample_id": sample.sample_id,
        "scenario": sample.scenario,
        "case_id": sample.case_id,
        "pair_mode": sample.pair_mode,
        "left_label": sample.left_label,
        "right_label": sample.right_label,
        "reference_video": sample.reference_video_relative,
        "generated_video": sample.generated_video_relative,
        "preview_image": sample.preview_image_relative,
        "action_path": sample.action_path_relative,
        "votes": {
            "action_following": action_vote,
            "visual_quality": visual_vote,
            "temporal_consistency": temporal_vote,
        },
        "artifact_flags": flags,
        "artifact_latest_s": flags[-1]["timestamp_s"] if flags else None,
        "note": note_text.strip(),
    }
    output_path = append_annotation(results_dir=results_dir, record=record)
    return _status_message(
        f"Saved `{sample.sample_id}` to `{_display_path(output_path)}`. "
        "Use Next sample to continue."
    )


def _sample_outputs(*components: Any) -> list[Any]:
    return list(components)


def _sample_title(sample: Sample, sample_index: int, sample_count: int) -> str:
    return (
        f"## Sample {sample_index + 1} / {sample_count}\n"
        f"`{sample.sample_id}`"
    )


def _sample_metadata(sample: Sample) -> str:
    reference_meta = sample.reference_video_meta or {}
    generated_meta = sample.generated_video_meta or {}
    width = generated_meta.get("width") or reference_meta.get("width")
    height = generated_meta.get("height") or reference_meta.get("height")
    fps = generated_meta.get("fps") or reference_meta.get("fps")
    duration_s = generated_meta.get("duration_s") or reference_meta.get("duration_s")
    control_mode = sample.action_summary.get("control_mode", "unknown")

    parts = [
        f"**Scenario:** `{sample.scenario}`",
        f"**Case ID:** `{sample.case_id}`",
        f"**Pairing:** left=`{sample.reference_video_relative}` | right=`{sample.generated_video_relative}`",
        f"**Action file:** `{sample.action_path_relative}`",
        f"**Preview still:** `{sample.preview_image_relative or 'missing'}`",
        f"**Inferred control regime:** {control_mode}",
    ]

    if width and height:
        parts.append(f"**Resolution:** {width}x{height}")
    if fps:
        parts.append(f"**FPS:** {fps:.2f}")
    if duration_s:
        parts.append(f"**Duration:** {duration_s:.2f}s")

    return " | ".join(parts)


def _artifact_markdown(flags: list[dict[str, Any]]) -> str:
    if not flags:
        return FLAG_HELP

    lines = ["**Flagged artifact times**"]
    for index, flag in enumerate(flags, start=1):
        lines.append(f"- {index}. `{flag['timestamp_s']:.3f}s` via {flag['source']}")
    return "\n".join(lines)


def _status_message(message: str) -> str:
    return f"**Status:** {message}"


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the Minecraft LM-Arena baseline app.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repo_root / "arena" / "manifest.json",
        help="Path to the normalized manifest JSON file.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=repo_root / "arena" / "results",
        help="Directory for JSONL annotation logs.",
    )
    parser.add_argument(
        "--rebuild-manifest",
        action="store_true",
        help="Re-scan data_subset and rebuild the manifest before launch.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        help="Host interface for Gradio.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        help="Port for Gradio.",
    )
    parser.add_argument(
        "--disable-writes",
        action="store_true",
        default=_env_flag("ARENA_DISABLE_WRITES", False),
        help="Disable writing annotations to disk.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = ensure_manifest(manifest_path=args.manifest, rebuild=args.rebuild_manifest)
    manifest = load_manifest(manifest_path)
    demo = build_app(
        manifest=manifest,
        results_dir=args.results_dir,
        writes_enabled=not args.disable_writes,
    )
    demo.launch(server_name=args.host, server_port=args.port)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
