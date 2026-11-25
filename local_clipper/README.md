# Local clipper

Run with Python 3.10+ on Windows and the local OpenShorts server on port 8000. Use a dedicated intake directory on an NTFS volume with sufficient free space. Only direct `.mp4` and `.mkv` children are scanned. The operator must have rights to every input.

The tracked Compose files retain the standard configuration. For this machine's local deployment, keep `docker-compose.local.yml` untracked and pass all three files explicitly when managing the service:

```powershell
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.local.yml config
```

The local override configures D: storage, the local selector, the fixed render policy, and the read-only intake mount. Provision the local intake token separately; never commit it or a file-specific mount. Check free space and the effective configuration before starting services.

```powershell
python local_clipper/clipper.py D:\clips\incoming watch
python local_clipper/clipper.py D:\clips\incoming watch --local-intake
python local_clipper/clipper.py D:\clips\incoming once --file pilot.mp4 --clip-range 0 8
python local_clipper/clipper.py D:\clips\incoming status
python local_clipper/clipper.py D:\clips\incoming retry --id LOCAL_JOB_ID
```

`--clip-range START END` explicitly selects source seconds and must last 5–180 seconds. This option is saved with the claimed job. Without it, the server selects moments using its configured local provider. Intake requires the service to attest the fixed full-frame/camera-band policy; automatic selection also requires a reachable configured selector. The worker does not silently switch selection modes. The camera detector can miss an inset, in which case the full source is fitted without an enlarged camera band. Review actual output for framing and editorial quality.

The watcher observes unchanged size and modification time for 30 seconds by default, checks Windows sharing, hashes and claims one file at a time, and records progress in `.local-clipper/state.sqlite3`. Stop it with Ctrl+C. The `--stable-seconds` and `--interval` options adjust observation and polling. `once --file NAME` waits for readiness and processes that root-level file; omit `--file` to take the first eligible file. Use `watch` for unattended discovery. Existing identical fingerprints are left untouched. Errors are recorded in SQLite and shown by `status`; console messages go to stderr, which may be redirected to a log file.

Successful, nonempty artifacts are downloaded to `clips/<local-id>`, checked against the HTTP content length, fully decoded by FFmpeg, and hashed. For ordinary intake, the source moves to `processed/<original-stem>_done<extension>` only after those checks; a collision gets a unique suffix before `_done`. An FFmpeg executable must be on PATH or installed with Streamlabs OBS at its standard location. Decode validation does not constitute editorial or visual QA. The source extension is retained. Failed ordinary inputs move to `failed/<local-id>`; `retry` explicitly retries a failed or interrupted upload with a fresh local locator. Review the recorded error first. A lost submission response or server error is `unknown_submission` and is never automatically retried: reconcile it with the service before any manual action. The worker does not publish clips.

The server copies uploaded sources to its upload volume. Check free space for that copy, temporary media and outputs before running; do not use this on a full drive. A killed service may lose pending upload sessions. The worker records a known backend job ID and resumes polling it after restart; it does not assert that the server itself can recover every job.

`--local-intake` opts automatic jobs into the local same-volume handoff. The claimed source must share an NTFS volume with `D:\clips\openshorts-local-inbox`; the worker hardlinks it there, and the backend reads it through a separate read-only mount. A locally provisioned token is required; no file paths or token values are passed as selection options. The worker checks identity and SHA-256 on registration, on resumed polling, and before archival. If the source changes, it stops and preserves the source. The backend cannot write through its read-only mount; these checks are not protection against a host administrator deliberately modifying and restoring the file between checks.

Handoff links are retained for backend restart and historical source lookup. They share the source's disk blocks, but retain those blocks even if another link is removed. Do not remove a handoff link while its job or source history is needed. Failed registration or an uncertain submission requires manual review; a consumed locator is never replayed. The standard streamed-upload mode remains available when `--local-intake` is omitted.

`--original` is a separate, operator-managed mode for one already hydrated original. It requires `once --local-intake`, a dedicated state/output root, and an explicitly provisioned exact-file read-only mount at `/data/original/source.mp4` with original intake enabled. The worker checks the original's fingerprint and leaves its name and location unchanged on both success and failure. After successful export and verification, stop access and detach the exact-file mount before any operator-requested rename or Dropbox availability change. An interrupted original-bound server job is not automatically resumed: preserve its state and reconcile it manually before retrying. A cloud-only placeholder must not be used as input.
