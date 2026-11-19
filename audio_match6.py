#!/usr/bin/env python3
"""Whole-source band-energy scan for clip1_hormozi.mp4, 2s-granularity first
pass over the FULL source (0-7747s), then fine scan at the top hits."""
import subprocess
import numpy as np

CONTAINER_SRC = "/tmp/windwaker_src.mp4"
CLIP = "/app/clip1_hormozi.mp4"
SR = 8000
WIN = 256

def load_pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    if ss is not None:
        cmd[2:2] = ["-ss", str(ss)]
    if t is not None:
        cmd[2:2] = ["-t", str(t)]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def band_env(x):
    n = len(x) // WIN
    segs = x[:n * WIN].reshape(n, WIN)
    spec = np.abs(np.fft.rfft(segs * np.hanning(WIN), axis=1)) ** 2
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    edges = np.logspace(np.log10(60), np.log10(3800), 9)
    env = np.zeros((n, 8))
    for i in range(8):
        m = (freqs >= edges[i]) & (freqs < edges[i + 1])
        env[:, i] = np.log1p(spec[:, m].sum(axis=1))
    return env

clip = load_pcm(CLIP)
ce = band_env(clip)
ce_n = ce / (np.linalg.norm(ce, axis=1, keepdims=True) + 1e-9)
n_c = len(ce_n)

def coarse(t0, tlen, stride_frames):
    src = load_pcm(CONTAINER_SRC, ss=t0, t=tlen)
    se = band_env(src)
    se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
    if len(se_n) <= n_c:
        return []
    # downsample envelopes by `stride_frames` (2s = 62 frames) for speed
    c = ce_n[::stride_frames]
    s = se_n[::stride_frames]
    nc = len(c)
    if len(s) <= nc:
        return []
    total = np.zeros(len(s) - nc + 1)
    nfft = 1 << int(np.ceil(np.log2(len(sb := s[:, 0]) + len(cb := c[:, 0])) + 1))
    for b in range(8):
        nfft_b = 1 << int(np.ceil(np.log2(len(s[:, b]) + len(c[:, b])) + 1))
        cc = np.fft.irfft(np.fft.rfft(s[:, b], nfft_b) * np.conj(np.fft.rfft(c[:, b], nfft_b)), nfft_b)
        m = min(len(total), len(cc))
        total[:m] += cc[:m]
    k = 8
    top = np.argpartition(total, -k)[-k:]
    top = top[np.argsort(total[top])[::-1]]
    hops = stride_frames * WIN / SR
    return [(t0 + float(l) * hops, total[l] / nc) for l in top]

hits = []
for t0 in range(0, 7600, 240):
    r = coarse(float(t0), 300.0, 62)
    hits.extend(r)
hits.sort(key=lambda x: -x[1])
print("TOP-10 coarse hits:")
seen = set()
shown = 0
for t, v in hits:
    bucket = int(t // 40)
    if bucket in seen:
        continue
    seen.add(bucket)
    print(f"  {t:10.2f}s  cos {v:+.4f}")
    shown += 1
    if shown >= 10:
        break

# fine scan the best bucket with full-resolution envelopes
best_t = hits[0][0]
print("fine scanning around", best_t)
src = load_pcm(CONTAINER_SRC, ss=max(0, best_t - 15), t=50.6 + 30)
se = band_env(src)
se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
total = np.zeros(max(1, len(se_n) - n_c + 1))
for b in range(8):
    nfft = 1 << int(np.ceil(np.log2(len(se_n[:, b]) + n_c)))
    cc = np.fft.irfft(np.fft.rfft(se_n[:, b], nfft) * np.conj(np.fft.rfft(ce_n[:, b], nfft)), nfft)
    m = min(len(total), len(cc))
    total[:m] += cc[:m]
top = np.argpartition(total, -3)[-3:]
top = top[np.argsort(total[top])[::-1]]
base = max(0, best_t - 15)
for l in top:
    print(f"  fine: {base + float(l) * WIN / SR:10.3f}s  cos {total[l]/n_c:+.4f}")