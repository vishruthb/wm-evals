from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np


KEY_NAMES = ["W", "S", "A", "D", "left", "right"]


@dataclass(frozen=True)
class ActionSegment:
    start_frame: int
    end_frame: int
    label: str


@dataclass(frozen=True)
class ActionSummary:
    n_frames: int
    fps: float | None
    duration_s: float | None
    used_keys: list[str]
    mouse_pitch_values: list[float]
    mouse_yaw_values: list[float]
    control_mode: str
    segments: list[ActionSegment]
    markdown: str


def load_action_file(action_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    payload = np.load(Path(action_path), allow_pickle=True).item()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict payload in {action_path}, found {type(payload)!r}")
    if "keyboard" not in payload or "mouse" not in payload:
        raise ValueError(f"Missing keyboard/mouse arrays in {action_path}")

    keyboard = np.asarray(payload["keyboard"], dtype=np.float32)
    mouse = np.asarray(payload["mouse"], dtype=np.float32)
    if keyboard.ndim != 2 or keyboard.shape[1] != len(KEY_NAMES):
        raise ValueError(f"Unexpected keyboard shape for {action_path}: {keyboard.shape}")
    if mouse.ndim != 2 or mouse.shape[1] < 2:
        raise ValueError(f"Unexpected mouse shape for {action_path}: {mouse.shape}")
    if keyboard.shape[0] != mouse.shape[0]:
        raise ValueError(
            f"Keyboard/mouse length mismatch for {action_path}: "
            f"{keyboard.shape[0]} vs {mouse.shape[0]}"
        )

    return keyboard, mouse[:, :2]


def build_action_summary(
    action_path: str | Path,
    fps: float | None = None,
    max_segments: int = 18,
) -> ActionSummary:
    keyboard, mouse = load_action_file(action_path)
    n_frames = int(keyboard.shape[0])
    duration_s = (n_frames / fps) if fps else None

    used_keys = [KEY_NAMES[i] for i in range(len(KEY_NAMES)) if np.any(keyboard[:, i] > 0.5)]
    mouse_pitch_values = _rounded_unique(mouse[:, 0])
    mouse_yaw_values = _rounded_unique(mouse[:, 1])
    control_mode = _infer_control_mode(keyboard, mouse)
    segments = _collapse_segments(keyboard, mouse)
    markdown = _format_markdown(
        n_frames=n_frames,
        fps=fps,
        duration_s=duration_s,
        used_keys=used_keys,
        mouse_pitch_values=mouse_pitch_values,
        mouse_yaw_values=mouse_yaw_values,
        control_mode=control_mode,
        segments=segments,
        max_segments=max_segments,
    )

    return ActionSummary(
        n_frames=n_frames,
        fps=fps,
        duration_s=duration_s,
        used_keys=used_keys,
        mouse_pitch_values=mouse_pitch_values,
        mouse_yaw_values=mouse_yaw_values,
        control_mode=control_mode,
        segments=segments,
        markdown=markdown,
    )


def summary_to_manifest_dict(summary: ActionSummary) -> dict[str, Any]:
    return {
        "n_frames": summary.n_frames,
        "fps": summary.fps,
        "duration_s": summary.duration_s,
        "used_keys": summary.used_keys,
        "mouse_pitch_values": summary.mouse_pitch_values,
        "mouse_yaw_values": summary.mouse_yaw_values,
        "control_mode": summary.control_mode,
        "segments": [asdict(segment) for segment in summary.segments],
        "markdown": summary.markdown,
    }


def _rounded_unique(values: np.ndarray) -> list[float]:
    rounded = {round(float(value), 3) for value in values.tolist()}
    return sorted(rounded)


def _infer_control_mode(keyboard: np.ndarray, mouse: np.ndarray) -> str:
    has_keyboard = bool(np.any(keyboard > 0.5))
    has_mouse = bool(np.any(np.abs(mouse) > 1e-6))
    if has_keyboard and has_mouse:
        return "keyboard + camera"
    if has_keyboard:
        return "keyboard-only"
    if has_mouse:
        return "camera-only"
    return "idle / unclear"


def _collapse_segments(keyboard: np.ndarray, mouse: np.ndarray) -> list[ActionSegment]:
    if keyboard.shape[0] == 0:
        return []

    labels = [_describe_step(keyboard[idx], mouse[idx]) for idx in range(keyboard.shape[0])]
    segments: list[ActionSegment] = []
    start = 0
    current = labels[0]
    for idx in range(1, len(labels)):
        if labels[idx] != current:
            segments.append(ActionSegment(start_frame=start, end_frame=idx - 1, label=current))
            start = idx
            current = labels[idx]
    segments.append(ActionSegment(start_frame=start, end_frame=len(labels) - 1, label=current))
    return segments


def _describe_step(keyboard_row: np.ndarray, mouse_row: np.ndarray) -> str:
    pressed_keys = [KEY_NAMES[idx] for idx, value in enumerate(keyboard_row) if value > 0.5]
    pitch = float(mouse_row[0]) if len(mouse_row) >= 1 else 0.0
    yaw = float(mouse_row[1]) if len(mouse_row) >= 2 else 0.0
    has_mouse = abs(pitch) > 1e-6 or abs(yaw) > 1e-6

    key_label = "+".join(pressed_keys) if pressed_keys else ""
    mouse_label = ""
    if has_mouse:
        mouse_label = f"mouse(pitch={pitch:+.1f}, yaw={yaw:+.1f})"

    if key_label and mouse_label:
        return f"{key_label} + {mouse_label}"
    if key_label:
        return key_label
    if mouse_label:
        return mouse_label
    return "idle"


def _format_markdown(
    n_frames: int,
    fps: float | None,
    duration_s: float | None,
    used_keys: list[str],
    mouse_pitch_values: list[float],
    mouse_yaw_values: list[float],
    control_mode: str,
    segments: list[ActionSegment],
    max_segments: int,
) -> str:
    timing_bits = [f"{n_frames} action steps"]
    if fps:
        timing_bits.append(f"{fps:.2f} FPS")
    if duration_s is not None:
        timing_bits.append(f"~{duration_s:.2f}s")

    lines = [
        f"**Action summary:** {' | '.join(timing_bits)}",
        f"**Inferred control mode:** {control_mode}",
        f"**Keys used:** {', '.join(used_keys) if used_keys else 'none'}",
        (
            "**Mouse values:** "
            f"pitch={_format_values(mouse_pitch_values)} | "
            f"yaw={_format_values(mouse_yaw_values)}"
        ),
        "",
        "**Timeline**",
    ]

    for segment in segments[:max_segments]:
        if fps:
            start_s = segment.start_frame / fps
            end_s = (segment.end_frame + 1) / fps
            prefix = f"`{start_s:.2f}s-{end_s:.2f}s`"
        else:
            prefix = f"`frames {segment.start_frame}-{segment.end_frame}`"
        lines.append(f"- {prefix}: {segment.label}")

    remaining = len(segments) - max_segments
    if remaining > 0:
        lines.append(f"- ... {remaining} more segments omitted for readability")

    return "\n".join(lines)


def _format_values(values: list[float]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(f"{value:+.1f}" for value in values) + "]"
