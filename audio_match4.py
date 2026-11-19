#!/usr/bin/env python3
"""Fast NCC: use FFT-based cross-correlation via scipy.signal (or numpy fft)
on one 120s source window vs the 50.5s clip. Returns top offsets."""
import subprocess
import numpy as np
import json as _json

CONTAINER_SRC = "/tmp/windwaker_src.mp4"
CLIP = "/app/clip1_hormozi.mp4"
SR = 8000

def load_pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    if ss is not None:
        cmd[2:2] = ["-ss", str(ss)]
    if t is not None:
        cmd[2:2] = ["-t", str(t)]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

clip = load_pcm(CLIP)
a = clip.astype(np.float64)
a -= a.mean()
na = np.sqrt((a * a).sum())

def scan(t0, tlen):
    src = load_pcm(CONTAINER_SRC, ss=t0, t=tlen)
    b = src.astype(np.float64)
    b -= b.mean()
    if len(b) < len(a):
        return []
    # cross-correlation via FFT (full)
    n = len(b) + len(a) - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    cc = np.fft.irfft(np.fft.rfft(b, nfft) * np.conj(np.fft.rfft(a, nfft)), nfft)
    # normalized: local energy of b at each lag
    # sliding sum of squares via cumsum
    e = np.concatenate(([0.0], np.cumsum(b * b)))
    lags = np.arange(0, len(b) - len(a) + 1)
    local_e = e[lags + len(a)] - e[lags]
    denom = na * np.sqrt(local_e)
    denom[denom == 0] = 1e-12
    vals = cc[lags] / denom
    k = 5
    top = np.argpartition(vals, -k)[-k:]
    top = top[np.argsort(vals[top])[::-1]]
    return [(float(t0 + l / SR), float(vals[l])) for l in top]

res = scan(1600.0, 300.0)
print("window 1600-1900:")
for t, v in res:
    print(f"  {t:10.3f}s  NCC {v:+.4f}")
best = max(res, key=lambda x: x[1])
# refine +-1.5s at 1/30s with direct scan using same method on smaller window
res2 = scan(best[0] - 2.0, 5.0 + len(clip) / SR)
print("refine:")
for t, v in res2:
    print(f"  {t:10.3f}s  NCC {v:+.4f}")
best2 = max(res2, key=lambda x: x[1])
with open("/app/output/.match_result.json", "w") as f:
    _json.dump({"offset": best2[0], "ncc": best2[1]}, f)
print("BEST", best2)