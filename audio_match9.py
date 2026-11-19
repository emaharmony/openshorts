#!/usr/bin/env python3
"""Match clip1_final_style (the 10-15-04:37 restyle of clip_1) to the source.
Same pipeline as the self-test that scored cos=1.0, so it's sound."""
import subprocess
import numpy as np

CONTAINER_SRC = "/tmp/windwaker_src.mp4"
CLIP = "/app/c1fs.pcm"
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

clip = np.frombuffer(open(CLIP, "rb").read(), dtype=np.float32).copy()
print("clip s:", len(clip)/SR)
ce = band_env(clip)
ce_n = ce / (np.linalg.norm(ce, axis=1, keepdims=True) + 1e-9)
n_c = len(ce_n)

# fine scan around 316 +- 25
src = load_pcm(CONTAINER_SRC, ss=290.0, t=105.0)
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
print("TOP-5 in 290-395 for clip1_final_style:")
for l in top:
    print(f"  {290.0 + float(l) * WIN / SR:10.3f}s  cos {total[l]/n_c:+.4f}")