#!/usr/bin/env python3
"""Targeted fine scan: 300-380s (the known vase-mansion region per a99e1bf5
clip_1 = 316.12-358.64). Full-res band envelopes, 8 bands, report top-3."""
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

src = load_pcm(CONTAINER_SRC, ss=295.0, t=90.0)
se = band_env(src)
se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
total = np.zeros(len(se_n) - n_c + 1)
for b in range(8):
    nfft = 1 << int(np.ceil(np.log2(len(se_n[:, b]) + n_c)))
    cc = np.fft.irfft(np.fft.rfft(se_n[:, b], nfft) * np.conj(np.fft.rfft(ce_n[:, b], nfft)), nfft)
    m = min(len(total), len(cc))
    total[:m] += cc[:m]
top = np.argpartition(total, -5)[-5:]
top = top[np.argsort(total[top])[::-1]]
print("TOP-5 in 295-385:")
for l in top:
    print(f"  {295.0 + float(l) * WIN / SR:10.3f}s  cos {total[l]/n_c:+.4f}")

# Also direct NCC probe at the a99e1bf5 c1 border 316.12
a = clip.astype(np.float64); a -= a.mean()
for cand in (314.0, 315.0, 316.12, 317.0, 318.0):
    s = load_pcm(CONTAINER_SRC, ss=cand, t=len(clip)/SR)
    b = s.astype(np.float64)[:len(a)]; b -= b.mean()
    n = min(len(a), len(b))
    denom = np.sqrt((a[:n]**2).sum() * (b[:n]**2).sum()) or 1e-12
    print(f"raw NCC at {cand}: {(a[:n]*b[:n]).sum()/denom:+.4f}")