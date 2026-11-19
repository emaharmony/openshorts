# Codex workflow for OpenShorts

## Turn a video link into finished clips

When a user supplies a YouTube or public Twitch VOD link and asks Codex to choose moments and make clips, run the full Codex-led selection and rendering flow through the OpenShorts MCP server. Do not stop after explaining how the flow works. Pass the exact URL as `source_url`; OpenShorts fetches the source. Do not browse to, download, transcribe, or summarize the linked video yourself. The supported sources for this flow are YouTube URLs, public Twitch VOD URLs (`twitch.tv/videos/<id>` or `twitch.tv/<channel>/video/<id>`), and videos uploaded through OpenShorts; if the user gives another kind of link, explain that it is unsupported and stop. Twitch clips and non-VOD pages are unsupported. Subscriber-only or otherwise restricted Twitch VODs may fail without access; do not request or use Twitch credentials, cookies, or tokens. Do not silently substitute a different source or switch to automatic selection.

If the user specifically asks OpenShorts to choose clips automatically, use `process_video` instead. That uses OpenShorts' own automatic moment selector, not Codex's transcript-based selection.

### One-time setup

This repository's `.codex/config.toml` connects Codex to the self-hosted endpoint `http://localhost:8000/mcp` and prompts before each workflow tool call. Codex app and CLI honor this project-scoped config only after the project is trusted. The local OpenShorts server must be running; its default self-hosted mode does not require an auth token. If the MCP tools are unavailable, check project trust and that the server is running, then point to `docs/architecture/agent-access.md`; do not pretend to have started a job. Hosted access is optional and requires an authenticated OpenShorts account via Codex MCP OAuth or a configured `osk_` bearer token. Once connected, the workflow uses prepare, transcript, render, status, and list tools; publishing stays excluded unless the user separately requests it.

### Run the workflow

### Fixed render policy

Every output uses the server's vertical full-frame band layout, with a detected
OBS camera inset enlarged into a dedicated lower band. OBS camera footage is
already composited into the gameplay frame, so the original small inset may
remain visible above while its detected crop appears below. Keep the full face
visible, preserve the source pixels, and do not mask or paint over them. Hooks
and OpenShorts-generated subtitles/captions are disabled. Do not remove text
already burned into the source. Do not send per-job output, caption, layout, or
hook settings.
The current MCP `render_selected_clips` implementation still hardcodes
`captions: true`; until the server is updated to enforce this no-caption policy,
do not claim that a render follows it or start a render that would add captions.
App-controlled Remotion renders preserve the full input frame with a blurred
fill behind it and discard caller zoom/effect transforms. When a clip has
speech, it remains uncaptioned. In fixed band mode the camera inset detector
also runs on already vertical sources; when found, the full gameplay frame is
preserved with its aspect ratio in the upper band and the detected camera crop
is placed below.

1. **Confirm processing rights before preparing the source.** A bare URL is not consent. If the user has not already established in this conversation that they own the content or have rights to process it, ask them to confirm before calling `prepare_video`. After confirmation, pass `confirm_rights: true` to both `prepare_video` and `render_selected_clips`; do not ask twice.
2. **Prepare transcription.** For a supported YouTube or public Twitch VOD URL, call `prepare_video` with the exact `source_url`. For an uploaded video, use its completed `upload_id`. Keep the returned `session_id` for the remaining steps. If the link is unsupported, or source download/preparation fails, explain the issue and stop.
3. **Wait for the transcript.** Call `get_transcript` with the `session_id`. While `status` is `processing`, wait for `retry_after_seconds` (or about five seconds if absent) and poll again. Stop and report the returned error if status is `failed` or the tool errors.
4. **Read every transcript page.** Once ready, read `segments` and continue calling `get_transcript` with `offset` set to the previous response's `next_offset` until `next_offset` is null. Use `limit: 250` to minimize calls. Account for every page when choosing clips; if the transcript is too large to retain verbatim, keep timestamped page summaries so selection still covers the full video.
5. **Choose five strong clips by default.** Use the full timestamped transcript to find distinct, self-contained moments with a clear hook and payoff. Avoid repeated topics, incomplete sentences, long setup without payoff, and overlapping ranges unless overlap is needed for context. Use source-time seconds. Each range must be 5–180 seconds and stay within `duration_seconds`. Provide a concise title and description; do not add `viral_hook_text`. If the user requested a clip count or style, follow that instead; never exceed the MCP limit of 15 clips.
6. **Render the selections.** Call `render_selected_clips` with the `session_id`, the selected `clips`, and `confirm_rights: true`. The server applies the fixed render policy above; do not send per-job output-format, caption, layout, or hook settings. If validation rejects a range, correct the affected range using the transcript and duration, then retry only when the correction is clear.
7. **Wait for finished output.** Poll `get_job_status` with the returned `job_id` every 30–60 seconds while status is `queued` or `processing`. Stop on `failed` and report the useful error/log details. When completed, use the returned clips (or `list_clips` if needed) and give the user each clip's title and the download URL or local path actually returned by MCP. Do not invent or promise a URL when the result only provides a path or no downloadable reference.

Do not publish clips to YouTube, TikTok, or another service unless the user separately asks for publishing and specifies the destination. If quota, plan, authentication, or MCP errors block a step, report the concrete blocker and any returned upgrade or connection instructions; do not silently fall back to automatic `process_video`, because that bypasses Codex's transcript-based selection.

