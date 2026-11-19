#!/usr/bin/env python3
"""audio_match7: fine scans around BOTH candidate regions (1834.75 & 1695.5),
plus band-peak offset voting for corroboration."""
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

def fine(t0, tlen, label):
    src = load_pcm(CONTAINER_SRC, ss=max(0, t0), t=tlen)
    se = band_env(src)
    se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
    if len(se_n) <= n_c:
        print(label, "window too small")
        return
    total = np.zeros(len(se_n) - n_c + 1)
    per_band_peak = np.zeros(8)
    for b in range(8):
        nfft = 1 << int(np.ceil(np.log2(len(se_n[:, b]) + n_c)))
        cc = np.fft.irfft(np.fft.rfft(se_n[:, b], nfft) * np.conj(np.fft.rfft(ce_n[:, b], nfft)), nfft)
        m = min(len(total), len(cc))
        total[:m] += cc[:m]
        # per-band peak offset (seconds)
        pb = cc[:m]
        if len(pb):
            k = int(np.argmax(pb))
            if total[k] == total.max():
                pass
            per_band_peak[b] = k * WIN / SR
    base = max(0, t0)
    top = np.argpartition(total, -3)[-3:]
    top = top[np.argsort(total[top])[::-1]]
    print(f"{label} base={base:.2f}:")
    for l in top:
        print(f"   {base + float(l) * WIN / SR:10.3f}s  cos {total[l]/n_c:+.4f}")
    med = float(np.median(per_band_peak))
    print(f"   band-peak median offset: +{med:.3f}s -> {base+med:.3f}s")

fine(1834.75 - 14, 50.6 + 28, "region 1834")
fine(1695.5 - 14, 50.6 + 28, "region 1695")
fine(1701.4 - 14, 50.6 + 28, "region 1701")
fine(1759.0 - 14, 50.6 + 28, "region 1759 (old spectral)")
fine(1735.4 - 14, 50.6 + 28, "region 1735 (old rms)")