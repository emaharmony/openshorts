#!/usr/bin/env python3
"""Ground-truth check: does source[1735.4 .. 1785.9] contain the vase scene?

No heavy ASR needed: the ORIGINAL CLIP's karaoke captions were whisper'd from
its own audio. Instead of re-transcribing, do direct waveform correlation of
multiple 10s chunks at candidate offsets (1735.4 from RMS-envelope + 1759
from the earlier spectral pass) and report the strongest exact-alignment
offset. Raw PCM NCC over the FULL 50.5s duration, sampled every frame.
"""
import subprocess
import numpy as np

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
n_c = len(clip)

def ncc_at(off):
    """Normalized correlation of clip vs source at source-time `off` (s)."""
    src = load_pcm(CONTAINER_SRC, ss=off, t=len(clip) / SR + 1)
    m = min(len(src), n_c)
    a = clip[:m].astype(np.float64)
    b = src[:m].astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    if denom == 0:
        return 0.0
    return float((a * b).sum() / denom)

for cand in (1735.43, 1759.0, 1745.0, 1750.0, 1755.0, 1760.0, 1765.0):
    r = ncc_at(cand)
    print(f"offset {cand:9.3f}  NCC {r:+.4f}")

# fine scan around the better coarse area
lo = 1730.0
hi = 1770.0
step = 1.0 / 30.0
best = (-2.0, None)
import time
t0 = time.time()
off = lo
while off <= hi:
    r = ncc_at(off)
    if r > best[0]:
        best = (r, off)
    off += step
print("best fine:", best, f"({time.time()-t0:.0f}s)")