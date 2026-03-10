# Minecraft LM-Arena Baseline

This app is a small local Gradio baseline for reviewing paired Minecraft videos from `data_subset/`.
It follows the current dataset shape first and does not add physics or causality tags yet.

## Inferred dataset format

- Each scenario folder in `data_subset/` contains 10 cases: `01` through `10`.
- Each case is paired by exact case id inside one scenario folder.
- The pairing used here is:
  - left: `{case_id}.mp4`
  - right: `{case_id}_wangame.mp4`
  - actions: `{case_id}_action.npy`
  - preview still: `{case_id}.jpg`
- `ptlflow/run_all_eval.py` and `ptlflow/visualize_results.py` both treat `{id}.mp4` as the reference / GT video and `{id}_wangame.mp4` as the generated WanGame output. The app follows that same convention.

## App behavior

- Loads one paired sample at a time from `arena/manifest.json`.
- Shows reference video on the left and WanGame output on the right.
- Displays a formatted action summary derived from `*_action.npy`.
- Collects three votes:
  - action following
  - visual quality
  - temporal consistency
- Each vote is `Left better`, `Right better`, or `Tie / unsure`.
- Includes a `Tie all / unsure` shortcut.
- Includes a manual `Flag artifact` flow:
  - pause the player
  - read the native video timestamp
  - type seconds into the artifact field
  - click `Flag artifact`
- Saves annotations to `arena/results/annotations.jsonl`.

## Files

- `app.py`: Gradio UI
- `build_manifest.py`: dataset scanner and manifest writer
- `dataset.py`: manifest loading and path resolution
- `actions.py`: action parsing and formatting
- `result_logger.py`: JSONL logging

## How to run

Install the minimal dependencies in your Python environment:

```bash
python -m pip install gradio numpy
```

Build or rebuild the manifest:

```bash
python arena/build_manifest.py
```

Run the app:

```bash
python arena/app.py
```

Optional flags:

```bash
python arena/app.py --rebuild-manifest --port 7861
```

Read-only mode for public demos:

```bash
python arena/app.py --disable-writes
```

Or with an environment variable:

```bash
ARENA_DISABLE_WRITES=1 python arena/app.py
```

## Limitations and ambiguities

- The current dataset naturally supports a fixed reference-vs-WanGame A/B pair, not a blinded model-vs-model arena.
- `.jpg` files look like aligned preview stills, but none of the relevant `ptlflow` evaluation scripts consume them. The app surfaces them only as metadata.
- `*_action.npy` contains `keyboard` `(T, 6)` and `mouse` `(T, 2)` arrays. The keyboard order is inferred from `ptlflow/action_flow_score.py` as `[W, S, A, D, left, right]`, and mouse order as `[pitch, yaw]`.
- In this subset, the `left` and `right` keyboard channels exist in the format but appear unused.
- Gradio’s stock video components do not provide a reliable cross-player live timestamp callback, so artifact flagging uses a documented manual timestamp fallback.
- The two video players are independent and not synchronized.
- If you deploy to Hugging Face Spaces, free storage is ephemeral. Local JSONL annotations are fine for local runs, but not a durable collection backend for a public deployment.

## If physics / causality tags are added later

- Extend the JSONL schema in `result_logger.py` with new tag fields.
- Add new controls in `app.py`; the manifest format does not need to change for simple extra labels.
- If the future setup compares multiple generated videos instead of reference vs generated, change the manifest schema first so samples can carry arbitrary candidate lists instead of the current fixed left/right pair.

## Spaces note

- `app.py` reads `GRADIO_SERVER_NAME` and `GRADIO_SERVER_PORT`, so it is safe to run on Hugging Face Spaces.
- If you want the published app to be review-only for now, set `ARENA_DISABLE_WRITES=1`.
