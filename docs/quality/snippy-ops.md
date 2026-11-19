# Snippy OpenShorts Ops

Server admin reference for the OpenShorts instance on Snippy. Read this when the MCP endpoint is unreachable, when deploying changes, or when admin work (env changes, restarts) is needed.

## Host & access

- **Host:** Snippy (Windows 11, AMD Ryzen 7 7735HS, 31GB RAM, RTX 4060 Laptop GPU)
- **SSH:** `ssh emaha@100.91.144.40` (MagicDNS: `snippy`, tailnet `taile2845b.ts.net`) — BatchMode works
- **Repo:** `C:\Users\emaha\Projects\openshorts` (volume-mounted into the container — code edits need only `docker compose restart backend`)
- Old IP `100.99.238.0` is dead (Tailscale reinstall ~2026-10-14)
- **Output dir (moved 2026-10-15):** `D:\clips\stelzon` — compose mounts it at `/app/output` (backend) and `/output` (renderer). Old location `C:\Users\emaha\Projects\openshorts\output` is GONE (robocopy /MOVE); compose backup at `docker-compose.yml.bak-20261015`. New jobs write to D: (224GB+ free); C: was down to 28GB.

## Services

| Service | Host port | Notes |
|---------|-----------|-------|
| backend (FastAPI + MCP) | 8000 | `/docs` Swagger; `/mcp` endpoint |
| frontend (vite dashboard) | 5175 | job list, clip editor, settings |
| renderer (Remotion) | 3100 | used for AI-shorts rendering |
| Ollama | 11434 | host process, NOT a container — `LaunchOllama` scheduled task (`ollama.exe serve`, /IT flag, created 10/28). Container reaches it via `host.docker.internal:11434` |

GPU: backend container has `cuda: True` (RTX 4060). `docker-compose.override.yml` carries both the `GPU: "1"` build arg and the nvidia device reservation — both are required (build arg alone installs CUDA libs but does not expose the device).

## Windows headless gotchas (hard-won, updated 10/29)

1. **SSH-spawned GUI apps die with the session.** Docker Desktop must be launched via a scheduled task with `/IT` (interactive token):
   ```
   schtasks /Create /F /TN LaunchDD2 /TR "\"C:\Program Files\Docker\Docker\Docker Desktop.exe\"" /SC ONCE /ST 23:59 /IT
   schtasks /Run /TN LaunchDD2
   ```
   Same pattern for Ollama (`LaunchOllama` → `ollama.exe serve`, direct exe — see LLM wiring section).
2. **Credential helpers break headless pulls** ("A specified logon session does not exist"). Fixed by renaming `docker-credential-desktop.exe` and `docker-credential-wincred.exe` to `.bak` in `C:\Program Files\Docker\Docker\resources\bin\`. Also: `docker run` of a fresh external image fails on credential-helper errors even after rename — use `docker exec` into existing containers for one-off tools (e.g. ffprobe) instead of `docker run`.
3. **First-run onboarding**: pre-created `%APPDATA%\Docker\settings-store.json` with `displayedOnboarding: true` to skip the GUI license dialog.
4. Over SSH, prefer writing PowerShell to a .ps1 file (scp it over) and running `powershell -ExecutionPolicy Bypass -File ...` — inline quoting from a mac will eat you alive. Escaping gotchas: `$_` must be `` `$_ `` inside double-quoted ssh one-liners; python heredocs don't survive inline — either scp a `.py` and `docker cp` it, or write via stdin pipe (`cat | ssh host "docker exec -i ... sh"`). `schtasks` via cmd is more quoting-tolerant — put complex /TR args in a `.bat` launcher.
5. **Long-running remote work:** `docker exec -d ... sh -c "nohup ... > /tmp/x.log 2>&1 &"` survives SSH disconnect; a bare `docker exec -d cmd` dies with the session.
6. **SSH flapping under load:** `kex_exchange_identification: Connection reset by peer` ~50% of attempts when Snippy is busy. Retry pattern: single attempts spaced 30–90s; rapid retry loops make it worse. Whole-machine dropouts (ping fails, ports closed) have recurred — usually recovers within the hour.

## Deployed patches (2026-10-14, all verified live in container)

1. **`SPEAKER_NOTE`** (pronouns): `speaker_note()` in `main.py` reads env, injected into `DETAIL_PROMPT_TEMPLATE` COPY RULES via `speaker_note` format field. Set in `.env`: `SPEAKER_NOTE=The streamer is a woman - use she/her.`
2. **`CAPTION_MARGIN_V`** (caption bottom margin): `subtitles.py` `SAFE_MARGIN_V` env-overridable; **loads `.env` itself at module import** (load-order bug fix). Set to 36 (TikTok-safe is 43 — revert if publishing direct to TikTok/Reels).
3. **Standing job prefs** are passed per-call by the skill (auto_hook=false etc.), not server-side.

Change flow: edit `.py` in repo → `docker compose restart backend` → verify inside container: `docker exec openshorts-backend python -c "import subtitles; print(subtitles.SAFE_MARGIN_V)"`.

## LLM wiring

Moment-picking runs on Snippy's local Ollama (no Gemini): `.env` has
`LLM_BASE_URL=http://host.docker.internal:11434/v1`, `LLM_MODEL=glm-5.3-flash:cloud`, `LLM_API_KEY=ollama`, `OLLAMA_CONTEXT_LENGTH=16384`.

**Ollama lifecycle (fixed 10/28):** runs as scheduled task `LaunchOllama` pointing DIRECTLY at "C:\Users\emaha\AppData\Local\Programs\Ollama\ollama.exe" serve (NOT `ollama app.exe` — the tray app's spawn hangs after reboots with a 0-byte server.log; direct exe + /IT works). Auto-starts at boot. If the moment-pick fails with `Gemini Error: [Errno 111] Connection refused` → `RuntimeError: Clip detection failed`, Ollama is down: kill any hung `ollama app.exe`, verify `ollama.exe serve` is running (`Get-Process ollama`), check LISTENING on 0.0.0.0:11434 with `netstat -ano | findstr 11434`, and verify the container chain: `docker exec openshorts-backend curl -s http://host.docker.internal:11434/api/version`.

**Firewall (fixed 10/28):** rule `Ollama 11434 (Tailscale only)` — TCP 11434, RemoteAddress 100.64.0.0/10, Private+Public profiles. The default ollama.exe rules are Public-only but the Tailscale NIC is Private-profile, which blocked mini→Snippy:11434 before this rule existed.

## Costs & limits

- Self-host: no quota, no watermark. Clip cost ≈ $0 (local LLM; whisper on GPU).
- Publish (`publish_clip`) needs an Upload-Post API key — not configured.
- fal.ai / ElevenLabs keys not configured (AI Shorts / dubbing won't work until added in dashboard Settings).

## If MCP is unreachable (triage order, updated 10/29)

1. `curl -m 5 http://100.91.144.40:8000/docs` from the mini — 200 means backend fine.
2. `ping 100.91.144.40` + `tailscale status | grep snippy` — distinguish machine-off (ping fails; often recovers on its own or after Ema nudges it — happened twice 10/28–10/29) vs sshd-down vs engine-down.
3. SSH (expect ~50% flaps under load — patient retry, sleep 30–90s, NEVER hammer), then `docker ps` — all three `openshorts-*` containers Up?
4. Docker engine down → `schtasks /Run /TN LaunchDD2` (~75s to healthy). Ollama down → `schtasks /Run /TN LaunchOllama`.
5. Container up but 500s: `docker compose logs backend --tail 50`.

## Storage & retention (as of 10/29)

- **Output:** `D:\clips\stelzon` (mounted `/app/output`) — ~7-day **retention window** (+OUTPUT_MAX_GB cap) auto-wipes old job dirs and sources; delivered links die with them. Gold refs are safe at `C:\Users\emaha\Videos\openshorts-references\`.
- **Uploads dir:** `C:\Users\emaha\Projects\openshorts\uploads\` (mounted `/app/uploads`) — upload slots + downloads land here (C:! not D:) — monitor free space; failed downloads leave multi-GB corpses; retention/`cleanup` doesn't always sweep them.
- Job sources (`<name>.mp4` inside each job dir on D:) are the re-render backbone — until retention gets them; move any you want to keep to `C:\Users\emaha\Videos\openshorts-references\`.

## Job dirs on disk

Each job: `/app/output/<jobid>/<name>.mp4` (source) + `<name>_clip_N.mp4` (clean reframe) + `subtitled_<ts>_<name>_clip_N.mp4` (captioned derivative) + `<name>_metadata.json` (transcript + shorts windows). `main.py -o .../part2` outputs land in a `part2/` subdir with plain `..._clip_N.mp4` names (no subtitle burn — caption via `/api/subtitle` after adding windows to the job's `shorts[]`).

## Deployed patches (2026-10-14, all verified live in container)

1. **`SPEAKER_NOTE`** (pronouns): `speaker_note()` in `main.py` reads env, injected into `DETAIL_PROMPT_TEMPLATE` COPY RULES via `speaker_note` format field. Set in `.env`: `SPEAKER_NOTE=The streamer is a woman - use she/her.`
2. **`CAPTION_MARGIN_V`** (caption bottom margin): `subtitles.py` `SAFE_MARGIN_V` env-overridable; **loads `.env` itself at module import** (load-order bug fix). **Currently 52** (was 36 until 10/27).
3. **`CAPTION_FONT_SIZE=28`** in `.env` (was 34 until 10/27).
4. Standing job prefs are passed per-call by the skill (auto_hook=false etc.), not server-side.
5. **Note:** server was Codex-refactored ~10/24 — `prepare_video`/`get_transcript`/`render_selected_clips`/`add_subtitles`/`create_upload` MCP tools added; `/api/clips` removed; **MCP paths hardcode `captions:false`**; REST `/api/process` multipart remains the captions-preserving entrypoint. Code edits still deploy via `docker compose restart backend` (repo is volume-mounted).
## Output storage (moved 2026-10-15)

`D:\clips\stelzon` — both compose mounts repointed (`D:/clips/stelzon:/app/output` backend, `D:/clips/stelzon:/output` renderer). Existing 6.87GB (226 files) robocopy /MOVE'd, so old clip URLs serve unchanged (verified 200 after remount). Backup of pre-move compose: `docker-compose.yml.bak-20261015`. **Retention sweeps this folder (~7 days + OUTPUT_MAX_GB cap)** — delivered links die with their files; gold refs live in `C:\Users\emaha\Videos\openshorts-references\` (protected).
