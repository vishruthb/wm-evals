# Dataset Notes

## Short assumptions

- Each folder under `data_subset/` is a scenario family, likely grouped by control regime or prompt generation regime rather than by evaluator split.
- Each scenario folder currently contains 10 complete cases: `01` through `10`.
- A complete case consists of:
  - `{id}.mp4`
  - `{id}_wangame.mp4`
  - `{id}_action.npy`
  - `{id}.jpg`

## What the files likely mean

- `{id}.mp4`
  - Most likely the reference / ground-truth video for that case.
  - This is not guessed only from the filename: `ptlflow/run_all_eval.py` and `ptlflow/visualize_results.py` explicitly pair `{id}.mp4` with `{id}_wangame.mp4` as reference vs generated.
- `{id}_wangame.mp4`
  - Most likely the WanGame-generated output for the same case.
- `{id}_action.npy`
  - A pickled dict with two arrays:
    - `keyboard`: shape `(77, 6)`
    - `mouse`: shape `(77, 2)`
  - From `ptlflow/action_flow_score.py`, the keyboard order is `[W, S, A, D, left, right]`.
  - From the same script, the mouse order is `[pitch, yaw]`.
  - The subset appears aligned at 77 frames per case, with videos observed at 25 FPS and about 3.08s duration.
- `{id}.jpg`
  - Likely a preview still or initial frame.
  - It visually matches the opening scene for at least one checked sample.
  - Relevant `ptlflow` scripts do not appear to use it for evaluation, so its exact role remains somewhat ambiguous.

## What each scenario folder likely represents

- `camera`
  - Inferred camera-only regime: no keyboard activity, nonzero mouse yaw throughout sampled files.
- `camera4hold_alpha1`
  - Inferred camera-only regime with held pitch/yaw steps.
- `1_wasd_only`
  - Inferred keyboard-only regime with no mouse input.
- `wasdonly_alpha1`
  - Another keyboard-only regime with no mouse input.
- `fully_random`
  - Mixed keyboard + mouse regime.
- `wasd4holdrandview_simple_1key1mouse1`
  - Mixed keyboard + mouse regime; folder name suggests sparse held inputs, which matches the action arrays broadly.

These scenario names were not documented elsewhere in the repo, so the descriptions above are inferred from folder names plus action statistics.

## Pairing logic

- Pair samples only within the same scenario folder.
- Pair by exact case id:
  - `scenario/01.mp4`
  - `scenario/01_wangame.mp4`
  - `scenario/01_action.npy`
- Do not pair across scenario folders even when the case ids match.

## Baseline UI choice

- The baseline app should be side-by-side A/B, not single-video scoring.
- Reason:
  - the dataset has a natural two-video pair per case
  - `ptlflow` already treats that pair as the main eval unit
  - the user requested an LM-Arena-style baseline first

## Important ambiguity

- This is an A/B comparison, but it is asymmetric:
  - left is a reference video
  - right is a generated WanGame output
- That means the UI is "arena-shaped" but not a blinded model-vs-model arena.
- A stricter single-video scoring flow would also be coherent, but the current repo structure supports paired comparison more directly, so the baseline chooses A/B.
