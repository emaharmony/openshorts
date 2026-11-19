#!/usr/bin/env python3
"""Step 2: copy the 4.49GB source to /tmp inside the container, then PUT it."""
import json, shutil, time, urllib.request, urllib.error, os

BASE = "http://localhost:8000"
SRC = "/app/uploads/Windwaker_playthrough!_(first_time_D).mp4"
TMP = "/tmp/windwaker_src.mp4"

if not os.path.exists(TMP):
    t0 = time.time()
    shutil.copyfile(SRC, TMP)
    print(f"copy took {time.time()-t0:.0f}s", flush=True)
print("tmp size:", os.path.getsize(TMP), flush=True)

def req(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        payload = resp.read().decode()
        return resp.status, (json.loads(payload) if payload.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

st, up = req("POST", "/api/uploads",
             {"filename": os.path.basename(SRC), "size": os.path.getsize(TMP)})
print("slot:", st, up, flush=True)
if st != 200:
    raise SystemExit(1)
uid = up["upload_id"]
put_url = up["upload_url"]

t0 = time.time()
r = urllib.request.Request(put_url, data=open(TMP, "rb"), method="PUT",
                           headers={"Content-Type": "application/octet-stream"})
resp = urllib.request.urlopen(r, timeout=3600)
putres = json.loads(resp.read().decode())
print(f"PUT done in {time.time()-t0:.0f}s:", putres, flush=True)

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
st, proc = req("POST", "/api/process", body, timeout=180)
print("process:", st, str(proc)[:500], flush=True)
if st >= 400:
    raise SystemExit(1)
job_id = proc.get("job_id")
print("JOB_ID", job_id, flush=True)

deadline = time.time() + 2400
while time.time() < deadline:
    time.sleep(30)
    st, s = req("GET", f"/api/status/{job_id}", timeout=120)
    txt = json.dumps(s)
    print(time.strftime("%H:%M:%S"), st, txt[:200], flush=True)
    if st == 200 and isinstance(s, dict) and s.get("status") in ("completed", "failed"):
        break

print("FINAL", job_id, flush=True)
