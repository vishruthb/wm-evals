from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def annotations_path(results_dir: Path) -> Path:
    return results_dir / "annotations.jsonl"


def append_annotation(results_dir: Path, record: dict[str, Any]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = annotations_path(results_dir)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True))
        handle.write("\n")
    return output_path
