# HID — pentakewl highlight intelligence (v8 compose line)

The v8 pipeline: Twitch VOD → transcript+signals → candidates → v8 band compose → structured QA.
This module is the **locked-geometry line** Ema approved — the upstream OpenShorts auto-reframe
(blur fill / PiP / chat column) is a different template and is NOT the pentakewl look.

## Pipeline (in order)
1. `signalminer.py` — ebur128 + scene-change signals from the source
2. `candidate_ranker.py` — coarse flags → ranked candidate moments
3. `narrative.py` + `director.py` — beat constraints → locked-baseline plan (adaptive knobs only:
   window trim, reaction hold; NO zoom/punch-in; hook overlays never rendered — policy in `hook_craft.py`)
4. `compose_v8.py` — renders per the **per-VOD calibration json** (mandatory — OBS scenes change per stream)
5. `qa_struct.py` — deterministic gates + repair table
6. `chatminer.py` — chat signals (graceful-absent, MIN_COMMENTS=200)
7. `rollout.py` — feature-flag (baseline/shadow/active; 'active' requires explicit Ema approval)

## The v8 look (locked)
Slim full-width CAM band on TOP (+hflip), DOMINANT gameplay band below, black canvas, even-ized
height. pw8 preset in `calib/pw8.json` → canvas 1080×1442 (cam 686 / game 756).

## Per-VOD calibration
- OBS geometry changes per stream AND within a stream (scene changes). Probe ≥5-7 timepoints
  (frame grabs + vision), write `calib/<vod>.json` with segments[].cam/game crop boxes.
- f38 (11/18 VOD) draft committed — verify per-pick before compose.
- Head-safety beats slimness: if the cam band clips heads, grow the band (pad upward).

## Paths
No absolute paths: modules resolve their own dir; outputs go to `HID_WORK` env or the module dir.
