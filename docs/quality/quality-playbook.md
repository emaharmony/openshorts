# Clip Quality Playbook (stelz0n + pentakewl) — pre-flight briefing for fresh sessions

> Purpose: Ema asked to "train Lumi prior" so a cleared session starts at full clip quality.
> This is the distilled, verified playbook. Load order: this file → SKILL.md → references/blueprint.md.
> **v4 update (2026-11-11):** pentakewl pipeline updated for VOD 2923641711 campaign — per-VOD cam calibration (layout differs per VOD!), v8 swapped-ratio standard (game 64% / cam 36%), stream-slim download recipe with source-res probing, transcript-mining via Snippy uploads (captions=false, ignore auto-picks). Evidence base: 20 stelz0n B-2 clips + 25 pentakewl PV2 clips across 2 VODs, all vision-verified.

## §0 Agent Reference (any agent harness — start here)

**Identity map (affects all framing/pronoun settings):** `stelz0n` = Kirbii (female streamer → she/her); `pentakewl` = Ema himself (he/him). These are two distinct OBS situations, not one template.

**Decision tree — which pipeline:**
1. Source is stelz0n VOD, standard 3-band B-2 output acceptable → server-path B-2 recipe (§stelz0n / blueprint Layout B-2; captions must be burned on Snippy — mini ffmpeg lacks ass/drawtext).
2. Source is pentakewl (fullscreen-cam OBS, moving/repositioned cam overlays) OR any custom multi-band geometry → **mini-side compose** (§pentakewl compose, `b2renders/*.py`), captions: **NONE** (Ema adds them in TikTok; do NOT request the `/api/subtitle` round).
3. Any fresh VOD needing transcription/auto-picking → Blueprint Path 1/Path 2 (muxed-720p-only Twitch VODs fail Path 1 → Path 2).

**Environment map (resolve all hosts before starting):**
- Mini (local composer): ffmpeg + Python3 in `/usr/bin`; scratch in workspace `b2renders/`; all geometry from `penta_v2_windows.json` / window ledger files (authoritative)
- Snippy (`emaha@100.91.144.40`, Windows laptop): OpenShorts server on :8000, MCP on `/mcp`, whisper/CUDA, caption burn
- Delivery for custom compositions: static host on the **mini** (`python3 -m http.server 8399 --bind 0.0.0.0`, Tailscale-reachable at `100.124.195.86:8399`) — NOT OpenShorts output dirs (sweeper deletes unregistered files within the hour → user 404 = "nothing shows")
- Snippy-only rule: file ops on Snippy go through **Codex (gpt-5.5)**, never SSH manual edits (standing rule)

**Universal hard rules (any harness, any pipeline):**
- QA bar: batch avg ≥ 8.5, per-clip ≥ 8.0, all hard gates pass — evidence-based, vision-verified; only post links when passed
- Every feature/batch must be tested before moving on; no "should work" — curl-verify every URL
- Vision-QA rate limit: ≤3–4 frames per image call, 90–240s cooldown between calls
- Geometry: never re-derive from memory when a ledger file exists; verify against source frames when it doesn't
- **Ratio is Ema-locked (11/11): gameplay ~64% / webcam ~36%;** layout + cam box calibrated per VOD, never assumed

## Verified pipeline (3 steps, all evidence-backed from 20 delivered B-2 clips)
1. **Trim/extract** — `b2renders/e2_batch.py` (state-tracked via `e2_state.json`; retry-safe, per-clip job dirs)
2. **Compose** — `b2renders/compose_e_v3.py` (v3 filter_complex; **window ledger files in b2renders/ are authoritative — do not re-derive geometry from memory**)
3. **Recut exact** — `b2renders/recut_exact.py` (frame-accurate finals → `e2final_*.mp4` → `e2named/` for delivery)

## Hard rules that survived 20 clips (violating any = rework)
- **45s minimum duration floor** — staging clips shorter than 45s break the pipeline (frame availability)
- **Compose starts black on frame 0** — always verify first-frame content after compose before accepting output
- **mini ffmpeg lacks ass/drawtext** — caption burn-in must happen on Snippy, never on the mini
- **No SSH manual edits on Snippy** — use Codex (gpt-5.5) for all Snippy file ops (standing rule)
- **Delivery routing (updated 11/09):** stelz0n server jobs = URL links to `/videos/<job>/...` (or Dropbox `D:\Dropbox\Stream\Clips\clips to review` when Ema asks for files); custom mini-side composites = mini static server `:8399` (§0 env map). Discord announcements via `openclaw message send --channel discord`; custom-composite links go bare, one per line (Ema preference, 11/09).
- **VOD discovery:** stelz0n Twitch VODs via twitch API (A=2911679749, B=2912684252 precedent)
- **Review loop:** render → Ema reviews in Dropbox → notes → one adjustment round → final. Don't batch-adjust without his review.

## Quality levers (what actually moved the needle on v3)
- **Geometry via window ledger** (per-camera x/y/w/h) — v3 supersedes v1/v2 entirely; never mix
- **Adaptive caption styling** per clip energy, not one-size (stelz0n captions only; pentakewl = agent adds none — Ema captions in TikTok)
- **Audio normalizing before compose**, not after
- **Batch with state tracking** (e2_state.json pattern) so retries never double-render

## stelz0n (Kirbii) path — server-composed B-2
Use when the standard 3-band stack is acceptable and captions should be burned server-side.
- Layout args: `layouts=["screencast"]` always for stelz0n; `auto_hook: false`; captions via REST path
- B-2 stack (locked 10/30): game strip / full-bleed facecam band / black karaoke stage — see blueprint Layout B-2 recipe
- 45s material floor applies to any server-passed compose (hard server rejection below it); tail-pad then trim

## pentakewl (Ema) path — mini-side compose (updated 2026-11-11, v8 Ema-confirmed "perfect")
Full pipeline for Ema's own stream. **Layout is PER-VOD, not fixed**: the 11/8 VOD = top-left facecam + baked chat (batch 1–2 + E-batch); the 11/9 VOD = facecam bottom-right, no chat (F-batch). Never assume yesterday's layout — calibrate each VOD before composing. Evidence: 35 delivered PV2 clips across 2 VODs; 8 geometry iterations with Ema reviews (v5 → v6 balance → **v8 swapped ratio, current standard**).

1. **Source acquisition:** direct VOD download, stream-slimmed in flight (`ffmpeg -i <resolved HLS> -c:v libx264 -preset veryfast -crf 21 -maxrate 4500k -c:a aac -b:a 192k` — no `-vf scale` on a 720p-native source; keep output under 2048MB upload cap, else `-t 5129.98` split-copy into halves). Resolve the signed `chunked/index-dvr.m3u8` via yt-dlp (no auth needed). **Probe source res before promising anything:** concat `init-0.mp4` + a segment and ffprobe it — "chunked" is NOT always 1080p (11/9 VOD = 720p@4.5Mbps native; nothing exists server-side above it — set expectations with Ema, don't silently upscale).
2. **Window mining:** transcribe via Snippy (create_upload → PUT → `POST /api/process` multipart `captions=false target_clips=5` — transcripts land in `<job>_metadata.json` → `transcript.segments`; server's own auto-clip picks are IGNORED for pentakewl). Mine speech-dense windows: rank 50s bins by chars/s (`len(text)` summed per 10s bin from segments), require ≥25 word-events, spread picks 150–240s apart, pull from BOTH halves (5+5).
3. **CV layout detection (MANDATORY before geometry):** detect webcam position per VOD via vision, not assumption. Verify the exact cam box with a **zoomed vision read** (2× zoom of the suspect region) on BOTH halves — cam box can differ between VODs ([930,453]→[1280,720] on 11/8 vs [949,451]→[1280,701] on 11/9) and can move mid-stream (​11/8 had topleft + moved segments). Brightness profiles fail (vine decor + couch shadows defeat them). Face-detect alone also fails on neon/dark frames — YuNet 0-faces ≠ cam absent; confirm by vision.
4. **Geometry selection (v8 current standard, "swap the ratio"):** **Gameplay ~64%, webcam ~36%** (game is the star):
   - **Cam band:** crop the cam box *tight around heads* (e.g. 11/9: `crop=332:215:949:451` hflip → `scale=1080:699` at top). Full-head verification is mandatory: a 1.33-aspect box at full width runs tall (813px and 61% of frame = "overpowering", Ema rejection 11/11); side-cropping to ≤215px source height clears both crowns/chins. Vision-verify crown+chin of BOTH streamers before locking a tighter crop.
   - **Game column (single, under the cam):** everything left of the cam, full remaining height, scaled to 1080 wide (11/9: `crop=568:661:380:40` → `scale=1080:1264`). Carries the dialogue box naturally; 1.9× upscale hides well on painterly game art. Stop the crop exactly at the cam's left edge (x948 vs cam 949 — leaks 1–2px bleeds otherwise; top-left corner slivers are also possible: check corners).
   - Canvas = cam + game + 2px seam (11/9: 1080×1964). No black stage/tail ever (Ema, 11/09).
   - **Ratio history (all Ema-reviewed):** v5 = cam 61/game 39 ("webcam overpowering", rejected) → v6 L-shaped two-piece game 52/48 ("still off", rejected) → **v8 single-column 64/36 = locked**. When Ema tweaks ratio wording, prototype ONE clip first, vision-verify, then rebatch — never rebatch all 10 blind.
   - **hflip the cam** (raw is mirrored); **vine/leaf decor stays** (Ema: "looks good"); no captions; no hook text.
5. **Compose (mini):** ffmpeg filter_complex per clip (v8 pattern in memory/2026-11-11.md); audio AAC 192k; `setsar=1`; verify first frame is content, not black.
6. **QA gate:** vision-check frames ≥3 timestamps per clip: both faces present (face-detect weak on neon/dark — vision is the arbiter), un-mirrored, no cam bleed at column edges, no duplicate cam, edge-to-edge fill, dialogue box legible, clean audio. Bar: batch avg ≥8.5 / per-clip ≥8.0 (v8 example: 8.5/10 pre-ship).
7. **Deliver:** host on mini static server (§0 env map) — **never** OpenShorts output dirs (retention sweeper deletes unregistered files within the hour). Verify every URL 200. Bare links, one per line.
8. **Review loop:** render → Ema reviews → notes → one adjustment round, prototype-first. Black-tail removal, cam-band promotion, and the v8 ratio swap all came from his review — don't batch-adjust without it.

### PV2 geometry archive (verified per VOD)
| VOD / campaign | Layout | Cam crop (src→dst) | Game (src→dst) | Canvas | Status |
|----------------|--------|--------------------|----------------|--------|--------|
| 2922715864 (11/8) E-batch, C/D topleft | A | `crop=368:248:0:0, hflip, scale=1080:728` | `crop=872:610:380:40 → 1080:775` | 1080×1550 | superseded |
| 2922715864 (11/8) D04/D05 moved | B-old | `crop=350:267:930:453, hflip, scale=1080:822` | `crop=872:409:380:40 → 1080:507` | 1080×1332 | superseded |
| 2923641711 (11/9) **F-batch = CURRENT** | B-v8 swap | `crop=332:215:949:451, hflip, scale=1080:699` | `crop=568:661:380:40 → 1080:1264` single column | 1080×1964 | **LOCKED** |

## Session hygiene for clip work
- Start clip runs in a FRESH session (this playbook + SKILL.md + blueprint auto-loaded)
- Keep #sys-manager talk separate from render sessions — render output floods context
- b2renders/ intermediates: purge superseded campaigns only with Ema's explicit OK (11/11 purge: 8.7GB cleared on his word — download always happens AFTER cleanup, never before)
- The :8399 static server dies when the mini sleeps — wrap in `caffeinate -i` (and note the wrapper must be started detached: `nohup caffeinate -i python3 -m http.server 8399 --bind 0.0.0.0 & disown`); re-verify URLs before every delivery
- Never bare `git add -A` in the workspace (intermediates hang it; path-scoped adds only)
