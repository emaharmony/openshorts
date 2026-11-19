#!/usr/bin/env python3
"""Rerun job: rebuild 95708adc clip_1 (the vase scene) as a hooked+subtitled clip.

Pipeline (all inside openshorts-backend):
1. PUT /app/uploads/Windwaker...mp4 -> /api/uploads/<id> (localhost, fast)
2. POST /api/process {upload_id, layouts:["screencast"], captions:"auto",
   auto_hook:true, target_clips:1, clip_min_seconds:40, clip_max_seconds:70,
   acknowledged:true}
   -> 1 clip, vision-based selection biased to 40-70s
3. Poll job; if the picked clip isn't the vase scene (166s window), re-run
   with narrower bounds nudged toward the transcript anchor.
"""
import json
import math
import os
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
SRC = "/app/uploads/Windwaker_playthrough!_(first_time_D).mp4"
STATE = "/app/output/.rerun_state.json"


def req(method, path, body=None, timeout=300, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        payload = resp.read().decode()
        if raw:
            return resp.status, payload
        return resp.status, (json.loads(payload) if payload.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


st, up = req("POST", "/api/uploads", {"filename": os.path.basename(SRC), "size": os.path.getsize(SRC)})
if st != 200:
    print("slot failed:", st, up)
    raise SystemExit(1)
uid = up["upload_id"]
url = up["upload_url"]
print("slot:", uid)

# stream the file to the PUT endpoint
t0 = time.time()
r = urllib.request.Request(url, data=open(SRC, "rb"), method="PUT",
                           headers={"Content-Type": "application/octet-stream"})
resp = urllib.request.urlopen(r, timeout=1800)
putres = json.loads(resp.read().decode())
print(f"PUT done in {time.time()-t0:.0f}s:", putres)

body = {
    "upload_id": uid,
    "acknowledged": True,
    "layouts": ["screencast"],
    "output_format": "vertical",
    "target_clips": 1,
    "clip_min_seconds": 40,
    "clip_max_seconds": 70,
    "auto_hook": True,
    "auto_hook_style": "pill",
    "captions": "auto",
}
st, proc = req("POST", "/api/process", body, timeout=120)
print("process:", st, str(proc)[:400])
if st >= 400:
    print("FAILED at /api/process")
    raise SystemExit(1)

job_id = proc.get("job_id")
print("JOB_ID", job_id)
with open(STATE, "w") as f:
    json.dump({"job_id": job_id, "upload_id": uid}, f)

# poll
deadline = time.time() + 1800
while time.time() < deadline:
    time.sleep(30)
    st, s = req("GET", f"/api/status/{job_id}", timeout=120)
    text = json.dumps(s)
    m = [k for k in ("status",) if k in str(s)]
    print(time.strftime("%H:%M:%S"), st, str(s)[:220])
    done = '"completed"' in text or '"status": "completed"' in text.lower()
    if done or st == 404:
        break

print("FINAL:", job_id)