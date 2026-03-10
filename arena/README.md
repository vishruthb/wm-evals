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
