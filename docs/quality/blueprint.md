# Generation Blueprint & QA Checklist

Read this BEFORE starting any clip generation and run the QA section AFTER every batch. Updated 2026-10-29 from the Wind Waker 20-clip deployments (10/28–10/29). Supersedes all earlier versions.

## Ema's standing targets (updated 2026-10-28)

- **QA bar: 8.5+ rubric average per batch** (raised from 7.5)
- **10 clips per VOD** (raised from 5) — for top-ups, see the two render paths below
- **Batch average ≥ 8.5 required to post.** Weakest delivered clip so far: 8.2. If a batch mines below 8.5, drop weak clips and mine more windows rather than delivering filler.

## The Template (locked — Ema: "that's perfect, that's how I want it forever", 2026-10-22)

**Visual truth (verified against gold refs, 10/28):** vertical 9:16 stack = gameplay band (top ~50%, with small corner facecam inset top-right) → hard black divider → full-width large facecam band (~52–87%) → solid black bottom bar. Karaoke captions (heavy Anton, white + yellow active word) inside the cam band's lower third.

- **Face appears TWICE by design** (corner inset + large facecam band). This is the template signature, NOT a bug. Never "fix" it.
- **Band fill adapts to source:** fullscreen-cam OBS sources (pentakewl-style) → hard black bands; PiP-over-game sources (stelz0n) → blurred game fill between bands. Both are template-correct.
- **Caption env (server .env, live):** `CAPTION_FONT_SIZE=28`, `CAPTION_MARGIN_V=52`
- **NO hook text, ever** — `auto_hook: false` on every job. No burned titles/watermarks.
- **Pronouns:** server `.env` `SPEAKER_NOTE=The streamer is a woman - use she/her.` — verify it matches the actual streamer before any job; change via .env + `docker compose restart backend`.

**Gold reference clips:** `Snippy: C:\Users\emaha\Videos\openshorts-references\batch-2026-10-22-scarygame` (8 `subtitled_*_recut_*` clips, 10/22 scary-game batch). Old gold ref (95708adc Windwaker clip_5) is dead — retention wiped it. NEVER use old job outputs at D:\clips\stelzon as reference — they autowipe (~7 days).

## Model / pipeline stack (as of 2026-10-29)

| Stage | What runs | Where |
|-------|-----------|-------|
| Download | yt-dlp (Twitch/YouTube) | Snippy CPU |
| Transcription | **Whisper `large-v3-turbo` on CUDA** (faster-whisper, GPU-wired 10/27) — a 3973s VOD transcribes in ~25–35 min | Snippy GPU |
| Moment picking + titles/hooks | **`glm-5.3-flash:cloud`** via Snippy's local Ollama (`LLM_BASE_URL=http://host.docker.internal:11434/v1`, 2-pass: score → detail) | Snippy → Ollama (host.docker.internal from container) |
| Scene/face detect | OpenCV + mediapipe + YOLO (screencast_layout, split_layout, active_speaker) | Snippy CPU/GPU |
| Reframe + caption burn | ffmpeg + OpenCV 9:16 + ASS subtitles (reframe_v2), **fixed band layout baked server-side (Codex refactor ~10/24)** | Snippy, CUDA (RTX 4060) |
| Post-gen visual QA | Lumi vision check (image tool on the mini, glm-5.3-flash:cloud) | Mac mini |

Ollama on Snippy auto-starts via scheduled task **`LaunchOllama`** → `ollama serve` (/IT). If moment-pick dies with `Connection refused` to 11434 from inside the container, check Ollama first (see snippy-ops.md).

## Two render paths — pick by situation

### Path 1: Fresh VOD (default)
Works when the VOD has separate audio renditions or YouTube. **Known blocker for stelz0n Twitch VODs: muxed-720p-only HLS** (single rendition with h264+aac+`timed_id3` data stream) → yt-dlp postprocess dies with `Postprocessing: Conversion failed!` (reproduced 10/27 and 10/28). If Path 1 fails this way, **go straight to Path 2 — do not retry the same download.**

MCP call (only when captions via REST aren't needed — MCP `process_video` hardcodes `captions:false`; REST is preferred):
```
POST /mcp tools/call process_video {source_url, max_clips, confirm_rights:true, auto_hook:false, layouts:["screencast"]}
```
**REST (preferred — preserves captions):**
```
POST http://100.91.144.40:8000/api/process   (multipart)
  url=<VOD URL>, acknowledged=true, output_format=vertical,
  layouts=screencast, auto_hook=false, target_clips=10   (captions default ON)
```
Optional params seen in OpenAPI: `clip_min_seconds`, `clip_max_seconds`, `force_low_quality`, `max_minutes`, `webhook_url`. Returns `{job_id}` → poll `GET /api/status/<job_id>` (logs + result.clips with titles + `/videos/...` urls). `/api/clips` is GONE from the refactored server — use `/api/status` or MCP `list_clips`.

### Path 2: Slim re-encode + hand-picked top-up (proven 10/29; use for stelz0n VODs and for "N more clips" requests)
Bypasses re-downloads entirely by reusing the completed job's source mp4 (they persist at `/app/output/<jobid>/<name>.mp4` until retention wipes).

1. **Create upload slot from inside the container** (cap 2048 MB):
   `docker exec -i openshorts-backend sh -c "curl -s -X POST http://localhost:8000/api/uploads -H 'Content-Type: application/json' -d '{\"filename\":\"slim.mp4\"}'"` → `{upload_id, upload_url}`
2. **Slim re-encode inside container** (source = existing job-dir mp4):
   `ffmpeg -y -i '<source>.mp4' -map 0:v:0 -map 0:a:0 -c:v libx264 -preset veryfast -crf 24 -maxrate 3800k -bufsize 7600k -vf scale=1280:720 -c:a copy -movflags +faststart /tmp/<slim>.mp4`
   Run via `docker exec -d ... sh -c "nohup ... > /tmp/slim.log 2>&1 &"` and poll the log. A full 66-min VOD: ~5–9× realtime. Files >2048 MB cannot upload — that's the point of slimming.
3. **PUT the slim file to the upload URL** (from inside the container, localhost — fast).
4. **Pick windows:** hand-mine the transcript (`<jobid>_video_metadata.json` → `transcript.segments`) for dialogue-rich windows avoiding already-used ranges + `['s','']` dead zones. Or `prepare_video` MCP on the upload → auto transcript; windows 5–180s each, ≤15 per job.
5. **Render:** `POST /api/process` multipart with `upload_id=<upload_id>` + `acknowledged=true` + `output_format=vertical` + `layouts=screencast` + `auto_hook=false` + `captions=true` + `target_clips=5` (auto-picks) — **or** the faster no-re-transcribe path: `python3 main.py -i /tmp/<slim>.mp4 --selected-clips /tmp/sel.json -o output/<sessionid>/part2` with env `AUTO_CAPTIONS=1 AUTO_HOOK=0 HOOK_GROUNDING=0 SKIP_SCREENCAST_MODEL=1 SCREENCAST_LAYOUT=1 SPEAKER_NOTE='...'`. NOTE: the main.py selected-clips path **ignores AUTO_CAPTIONS** — clips come out caption-less; finish with step 6.
6. **Burn captions per clip:** copy part2 clips into the session dir as `<sess>_video_clip_N.mp4`, **append the windows to `shorts[]`** in `<sess>_video_metadata.json` (python inside container; index-based), then for each clip index: `POST /api/subtitle {"session_id":"<sess>","clip_index":N}` → returns `new_video_url` (subtitled_...mp4). ~40s/clip. This endpoint reuses the server caption style (28px/margin 52) and needs no re-transcribe.
7. Top-up delivery = original batch links + new subtitled links. Track a used-range ledger so windows never repeat across runs.

## Standing generation recipe (Ema-approved defaults, updated 2026-10-28)

- `auto_hook: false` — no burned hook text, captions only
- `layouts: ["screencast"]` for OBS game+corner-webcam VODs; **always pass it for stelz0n** (general layout slices the corner cam)
- **`target_clips: 10`** (Ema's bar since 10/28; top-ups via Path 2)
- `confirm_rights: true` always (required)
- Captions: default karaoke style via the REST path (`captions=true` multipart, default-on) — server .env carries `CAPTION_FONT_SIZE=28, CAPTION_MARGIN_V=52`
- Pronouns via server `SPEAKER_NOTE` (.env)
- Batch delivery bar: **average ≥ 8.5, each clip ≥ 8.0**, all hard gates pass

## Pre-generation checklist (before any render)

1. Stack reachable: `curl -m 5 http://100.91.144.40:8000/docs` → 200. If not, triage per references/snippy-ops.md ("If MCP is unreachable").
2. **Ollama up (moment-pick lives on it):** `docker exec openshorts-backend curl -s -m 5 http://host.docker.internal:11434/api/version` → `{"version":...}`. If refused — SSH to Snippy, check `Get-Process ollama`, log at `C:\Users\emaha\AppData\Local\Ollama\server.log`, relaunch via `schtasks /Run /TN LaunchOllama`. A dead Ollama kills the LLM moment-pick with `Gemini Error: [Errno 111] Connection refused → RuntimeError: Clip detection failed`.
3. SPEAKER_NOTE matches the actual streamer (if different person: update `.env`, `docker compose restart backend`).
4. **VOD-type check first (saves an hour):** stelz0n Twitch VODs are muxed-720p-only (single HLS rendition, h264+aac+timed_id3) → Path 1 dies at postprocess (`Conversion failed!`). Start Path 2 directly if a prior job's source exists. If the VOD is fully fresh, Path 1 once; on `Conversion failed!` pivot to Path 2.
5. Pass recipe args explicitly per call (auto_hook, layouts, captions) — never rely on MCP/defaults.
6. Upload endpoint caps at **2048 MB** — anything bigger must be slimmed before PUT.

## ALL STANDING RULES (consolidated index — updated 2026-10-29)

- **R1 — 10 clips per VOD** (raised from 5 on 2026-10-28). Top-ups mine fresh windows, never repeated ones.
- **R2 — QA bar: batch average ≥ 8.5 AND every clip ≥ 8.0**, all hard gates pass. Below bar → mine more windows and replace weak clips. No filler.
- **R3 — Locked template (never deviate):** **Layout B-2 (locked 2026-10-30, Ema pick)** — three-band stack, no inset: gameplay strip full-width top (~314px) + facecam band full-bleed (~835px, PiP box cropped from source at x870/y20/w388/h300) + black captions stage (~771px) carrying karaoke Anton captions (server style: white + #FFE500 active word, uppercase, ~24 chars/line). **Face appears ONCE.** (Previous face-dup inset template retired 10/30.) **No hook text, ever.** No watermarks. Recipe: `b2renders/batch.py` on the mini (deterministic ffmpeg compose → server captions); do NOT use server framing/rerender paths for B-2 (they re-run inset detection).
- **R4 — Layout args explicit per job:** `layouts=["screencast"]` for OBS-layout VODs (always for stelz0n); `auto_hook=false`; captions on via REST path (MCP hardcodes captions off).
- **R5 — Pronouns:** verify `SPEAKER_NOTE` matches the actual streamer BEFORE any run (currently: woman → she/her). Check in titles + captions at QA.
- **R6 — Rights gate:** `confirm_rights:true` only after confirmed rights (standing practice for Ema's approved streamers: stelz0n confirmed). A URL alone is not consent.
- **R7 — MANDATORY vision-QA gate before posting links:** frame-grab + vision-check (cam intact, captions on-frame, no hook), audio probe, title-vs-transcript, boundary check, verify every URL → 200/206. Evidence only — never "should work."
- **R8 — Retention:** outputs autowipe (~7 days). Every delivery message carries a "grab by <date>" warning. Gold refs are protected in `openshorts-references`.
- **R9 — Render paths:** Path 1 fresh VOD (REST `/api/process`); Path 2 slim re-encode + top-up. stelz0n/muxed-720p VODs fail Path 1 (`Conversion failed!`) — start Path 2 if a source exists; never burn time retrying Path 1.
- **R10 — Post-run bookkeeping:** update the used-window ledger, `memory-capture` new recipes/facts, clean `/tmp` QA frames/downloads on the mini, report blockers in-channel.

## Discord delivery & formatting rules

- **F1 — Batch header:** 📼 VOD name — batch avg **X.X**, clip count, then numbered clips.
- **F2 — Per-clip line:** `[Title](url) — score` + one-phrase verdict + 🔥 for any 9.0+. Titles as markdown links, never bare URLs.
- **F3 — Retention line at the bottom** of every delivery ("grab by <date>").
- **F4 — No ASCII tables under 4 columns** — use bullets (Ema preference). Tables only when 4+ columns and the grid genuinely helps.
- **F5 — QA evidence stays internal** (frame dumps on the mini); deliver only links + scores + verdicts, not walls of analysis.

## Post-generation QA checklist (every batch, before posting links)

1. `GET /api/status/<job_id>` → per-clip: title + `/videos/<jobid>/<file>` (or MCP `list_clips` — same data).
2. Download each clip; probe: AAC audio present, `volumedetect` mean ≈ −18 to −22 dB, no dead audio.
3. **Frame-grab ≥3 clips/batch (mid + start + end)**: `ffmpeg -ss <t> -i clip.mp4 -frames:v 1 f.jpg`. Vision-check each (image tool, ≤3–4 frames/call, 90–240s cooldown between calls — the small VLM rate-limits hard):
   - Facecam fully visible, not sliced (face-duplication inset+facecam = template signature, PASS)
   - Karaoke captions (white + yellow active word) fully inside frame; single-word all-yellow at its active moment is CORRECT; white-only at sampled quiet moments is sampling noise — confirm with 2–3 frames before calling a FAIL
   - Banded layout correct (game + facecam bands; blur-fill vs black-bar both template-correct for the source type)
   - NO hook text or watermark
4. Title read: she/her pronouns, no hook phrasing, title matches the actual moment.
5. Boundary check: first/last-2s frames for mid-word/mid-action cuts (real FAIL) vs 1-frame fades (OK).
6. Score rubric from evidence. **Post only when: all hard gates pass, every clip ≥ 8.0, batch average ≥ 8.5.** Below bar: drop weak clips, mine new windows (Path 2 step 4), re-run. Never deliver filler to round out a count.
7. Verify EVERY link: `curl -s -o /dev/null -w "%{http_code}" -r 0-100 <url>` → 200/206. No exceptions, no "should work".
8. Post links with per-clip score + one-phrase verdict; note the ~7-day retention window in every delivery.

## Clip quality rubric (score every clip before posting)

Each clip: hard gates + 0–2 per dimension (10 max). Score from EVIDENCE, never vibes.

### Hard gates (any FAIL → do not post that clip; fix or discard)
- **Cam integrity** — streamer's face fully on-frame, not sliced by any edge/band.
- **Captions on-frame** — no caption pixel clipped at any edge, any sampled time.
- **Pronouns** — she/her only (current streamer).
- **Audio** — present, mean ≈ −18 to −22 dB, no dead stretches.
- **Content fidelity** — title describes what actually happens; no fabrication.
- **No hook text** — zero burned hook/title/watermark.

### Quality scores (0 = bad, 1 = meh, 2 = good)
| # | Dimension | 0 | 2 | How to check |
|---|-----------|---|---|---------------|
| 1 | Moment strength | dull fragment | funny/emotional/payoff, self-contained | transcript + title together |
| 2 | Title punch | flat/generic | scroll-stopping, specific | would YOU click it? |
| 3 | Framing | crowded/off-center/band glitch | clean, cam + game both readable | vision-check mid frames |
| 4 | Caption readability | clutter kills it, wrong size | readable at a glance, karaoke style | vision-check |
| 5 | Cut boundaries | mid-word ends, dead air | clean in/out | first/last-2s frames + transcript |

### Verdict bands (bar = 8.5+)
- **8.5–10:** ship, note score. 9.0+ gets a 🔥 in delivery.
- **8.0–8.4:** ship only if batch average still ≥ 8.5 AND all hard gates pass; otherwise replace via fresh top-up.
- **<8.0 or ANY gate fail:** do not post — recut/restyle/re-run, log the reason.

Batch delivery rule: **every delivered batch averages 8.5+, every clip ≥ 8.0, all hard gates pass**, per-clip scores listed in the delivery message.

## Known issues (updated 2026-10-29)

1. **stelz0n VODs = muxed-720p-only HLS** (h264+aac+timed_id3 data stream) — yt-dlp postprocess dies `Postprocessing: Conversion failed!` on Path 1 (repro'd 10/27 AND 10/28). The timed_id3 stream poisons mp4 remuxing. Use Path 2. Also broke: upload-path PUTs >2048MB (`File too large`).
2. **Mic boom clipped at right edge of cam band** — in the RAW source feed (OBS framing), not a reframe bug. Unfixable.
3. **Docker doesn't auto-start on Snippy reboot** (Docker Desktop scheduled task `LaunchDD2` exists — manual `schtasks /Run /TN LaunchDD2` after reboots). Ollama DOES auto-start (LaunchOllama → `ollama.exe serve`, /IT flag, fixed 10/28).
4. **Per-segment band engagement (inset-only clips)** — two A-job clips on 10/28 rendered inset-only without the large facecam band for their segments (the mild form of the old corner-cam regression). Template face-dup clips were fine. If it reproduces on a delivered clip, re-render that window via Path 2.
5. **Caption karaoke-timing:** single-word captions go all-yellow at their active word ("POCAHONTAS", "why") — correct behavior, not a bug. Mid-frame white-only samples are timing artifacts; verify with multiple frames before flagging.
6. **Server was Codex-refactored ~10/24:** new MCP tools `prepare_video`/`get_transcript`/`render_selected_clips` (agent-picks flow) + `add_subtitles` + `create_upload`. `/api/clips` GONE — use `/api/status` or MCP `list_clips`. MCP process_video/render_selected_clips hardcode `captions:false`; REST `/api/process` multipart still takes `captions` (default on) + `layouts` + `target_clips` — REST is the caption path. `main.py --selected-clips` ignores `AUTO_CAPTIONS` env — finish via `/api/subtitle` (Path 2 step 6).
7. **Vision model cooldowns:** mini's image tool (glm-5.3-flash:cloud) intermittently aborts under rapid-fire calls — 90–240s sleeps between calls, ≤3–4 images per call.
9. **/api/source large-offset seek bug (found 10/30):** HTTP streaming of `/api/source/<job>` with input `-ss` > ~1000s returns WRONG-position content (asked for 7297.96s, got ~988s-scene content; 120s seek verified correct). Cause: source is served via a live ffmpeg pipe from position 0 — big input-side seeks over the pipe land at wrong positions. Workarounds: cut big-offset windows from server-native artifacts (the original `/videos` clips are pre-cut at the right windows), or keep source cuts to small relative offsets on files whose timeline starts at 0 (fresh top-up uploads).
10. **Vision model cooldowns still apply to QA on relayouts**: ≤3–4 frames per image call, 90–240s between calls — a rapid-fire relayout QA (6+ calls) gets frequent aborts; batch frames and wait between calls.

## Layout B-2 production recipe (locked 2026-10-30)

For stelz0n-style sources (full-frame gameplay + PiP cam top-right, 1280x720 slim):
1. **Compose mini-side (no server involvement):** cut window from `/api/source/<job>` (+50s tail-pad if window <50s), then ffmpeg stack: game strip `crop=1280:372:0:348→1080:314` top + cam box `crop=388:300:870:20→1080:835` middle + black base 1080x1920, audio from source. Reference impl: `~/workspace/b2renders/batch.py` (b2renders/batch.py on the mini).
2. **Captions server-side:** upload via `/api/uploads` + PUT, then `/api/process` with `output_format=horizontal` (passthrough — preserves the compose), `captions=true`, `auto_hook=false`, `target_clips=1`, `clip_min_seconds=50`, `clip_max_seconds=180`. Server transcribes fresh (Whisper) + burns locked karaoke style into the black stage.
3. **Trim tail:** server output may be ~5s short of padded length; trim locally back to the exact delivered window (`-t <dur>` re-encode crf20).
4. **Never** let the server's picker run on a B-2 video without `clip_min_seconds=50` — otherwise it re-picks a 25s sub-moment and changes content. Hard server floor: material <45s is rejected outright.
5. **Seek verification gate (added 10/30 after a bad batch):** `/api/source` HTTP cut with large `-ss` values (> ~1000s) can return WRONG-position content (content from ~988s scene when asking for 7297s — repro'd; 120s seek verified correct, so it's offset-dependent, likely live-pipe seek mangling). ALWAYS verify a source cut before processing: compare a frame from the cut file with a frame from the ORIGINAL delivered clip at the same timestamp (vision model). If they mismatch, do not process that window — re-plan the cut path.

## Deployed patches (change log)

- 2026-10-14: `SPEAKER_NOTE` env → `speaker_note()` in main.py → injected into DETAIL_PROMPT_TEMPLATE COPY RULES.
- 2026-10-14: `CAPTION_MARGIN_V` env override for `SAFE_MARGIN_V` in subtitles.py + dotenv load-order fix.
- 2026-10-15: standing prefs (auto_hook=false, 34px, margin 36) — now superseded: margins live in .env (28px/52 as of 10/27), standing prefs passed per-call here.
- 2026-10-22: locked template approved + gold refs saved to `C:\Users\emaha\Videos\openshorts-references\batch-2026-10-22-scarygame`.
- 2026-10-24: Codex-led server refactor (new MCP tool set, fixed band layout baked server-side, whisper large-v3-turbo/cuda wired).
- 2026-10-27: Ollama GPU/CUDA context verified end-to-end (container→host.docker.internal:11434); firewall rule added for Tailscale CGNAT range.
- 2026-10-28: Ollama LaunchOllama scheduled task fixed (direct `ollama.exe serve`, /IT); Tailscale-only firewall rule `Ollama 11434 (Tailscale only)` (TCP 11434, RemoteAddress 100.64.0.0/10); 20-clip delivery at new 8.5 bar.
- 2026-10-29: blueprint rewritten from the 20-clip deployments: 8.5 bar, 10/VOD, Path 2 (slim re-encode + /api/subtitle captions) documented, rubric bands recentered.
- 2026-10-30: Layout B-2 locked by Ema (replaces face-dup inset template): mini-side compose recipe + passthrough-captions server flow documented above; first relayout batch = the 20 delivered clips (A job 59138746-family + B job 79ccb762).
- 2026-10-30: server facts discovered during the first B-2 relayout run: (a) clip generation has a HARD 45s material floor — short windows must be tail-padded to ≥50s before `/api/process`, then trimmed back to exact length; (b) `/api/source` HTTP large-offset seeks (>~1000s) return WRONG-position content (A01/A02 batch cut from wrong scenes — caught at QA, batch quarantined); small offsets are correct. Both documented in the B-2 recipe + known issues.