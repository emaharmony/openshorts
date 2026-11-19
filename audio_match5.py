#!/usr/bin/env python3
"""Final alignment attempt with strict PCM equality:

The clip was re-encoded; exact PCM match is hopeless. Use MFCC-ish robust
features instead: log-mel-ish via simple band energies. Compute band-energy
envelope (20 log-spaced bands), then sliding dot-product (cosine) — much more
robust to codec differences than raw NCC.

If the true source window exists within 1600-1900s, cosine should exceed 0.8
at the correct offset while wrong offsets stay near zero.
"""
import subprocess
import numpy as np

CONTAINER_SRC = "/tmp/windwaker_src.mp4"
CLIP = "/app/clip1_hormozi.mp4"
SR = 8000
WIN = 256  # 32ms energy windows

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
    """Band energies per 32ms: log1p(energy in 8 log-spaced FFT bands)."""
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

def scan(t0, tlen):
    src = load_pcm(CONTAINER_SRC, ss=t0, t=tlen)
    se = band_env(src)
    se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
    n_c = len(ce_n)
    if len(se_n) <= n_c:
        return []
    # sliding cosine: correlate each of the 8 bands' envelopes, sum
    total = np.zeros(len(se_n) - n_c + 1)
    for b in range(8):
        cb = ce_n[:, b]
        sb = se_n[:, b]
        nfft = 1 << int(np.ceil(np.log2(len(sb) + len(cb))))
        cc = np.fft.irfft(np.fft.rfft(sb, nfft) * np.conj(np.fft.rfft(cb, nfft)), nfft)
        total += cc[:len(total)]
    k = 3
    top = np.argpartition(total, -k)[-k:]
    top = top[np.argsort(total[top])[::-1]]
    return [(float(t0 + l / SR * (WIN / WIN)), l * WIN / SR) for l in top], total, len(se_n) - n_c

# NOTE: l in the FFT result is in *frames* (32ms), convert properly.
res_frames, total, maxlag = scan(1600.0, 300.0)
print("top frames (approx):")
for t, l in res_frames:
    print(f"  frame {l} -> {t0 if False else 1600.0 + l * WIN / SR:9.3f}s")

# correct conversion; compute again cleanly
src = load_pcm(CONTAINER_SRC, ss=1600.0, t=300.0)
se = band_env(src)
se_n = se / (np.linalg.norm(se, axis=1, keepdims=True) + 1e-9)
n_c = len(ce_n)
total = np.zeros(len(se_n) - n_c + 1)
for b in range(8):
    cb = ce_n[:, b]
    sb = se_n[:, b]
    nfft = 1 << int(np.ceil(np.log2(len(sb) + len(cb))))
    cc = np.fft.irfft(np.fft.rfft(sb, nfft) * np.conj(np.fft.rfft(cb, nfft)), nfft)
    total += cc[:len(total)]
k = 5
top = np.argpartition(total, -k)[-k:]
top = top[np.argsort(total[top])[::-1]]
print("TOP-5 cosine hits:")
for l in top:
    t = 1600.0 + float(l) * WIN / SR
    print(f"  {t:10.3f}s  cos {total[l]/n_c:+.4f}")