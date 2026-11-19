#!/usr/bin/env python3
"""Cross-correlation matcher: exact RMS envelope alignment of clip vs source.

Simpler + more decisive than spectral peaks: 50ms-window RMS envelope, slide
the clip envelope across the source envelope (vectorized via stride tricks),
score = normalized MSE. Then verify with direct sample correlation at the
winner, comparing actual PCM.
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

def rms_env(x, win=400, hop=200):
    n = (len(x) - win) // hop + 1
    shape = (n, win)
    strides = (x.strides[0] * hop, x.strides[0])
    w = np.lib.stride_tricks.as_strided(x, shape=shape, strides=strides)
    return np.sqrt((w.astype(np.float64) ** 2).mean(axis=1))

clip = load_pcm(CLIP)
print("clip samples:", len(clip), len(clip) / SR, "s")

# Source segment around coarse guess 1759 +-30s
SEG_T0, SEG_LEN = 1700.0, 120.0
src = load_pcm(CONTAINER_SRC, ss=SEG_T0, t=SEG_LEN)
print("src seg samples:", len(src))

ce = rms_env(clip)
se = rms_env(src)
n_c = len(ce)
best = (1e18, 0)
for off in range(0, len(se) - n_c):
    seg = se[off:off + n_c]
    d = np.mean((ce - seg) ** 2)
    if d < best[0]:
        best = (d, off)
print("env best (MSE, seg-offset-s):", best, "->", SEG_T0 + best[1] * 0.025)

# verify with raw PCM normalized cross-correlation around that offset
off_s = int(best[1] * 0.025 * SR)
c48 = clip[:SR * 10] - clip[:SR * 10].mean()
region = src[off_s - SR:off_s + SR * 11]
region = region - region.mean()
cc = np.correlate(region, c48, mode="valid")
peak = int(np.argmax(np.abs(cc)))
print("raw PCM peak at", SEG_T0 + (off_s - SR + peak) / SR, "s, corr:", cc[peak] / np.abs(c48).sum() / 10)

t_off = SEG_T0 + (off_s - SR + peak) / SR
print("OFFSET_SECONDS", t_off)
with open("/app/output/.match_result.json", "w") as f:
    json.dump({"offset": float(t_off), "corr": float(cc[peak])}, f)