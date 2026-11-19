#!/usr/bin/env python3
"""Audio-fingerprint match: where does clip1_hormozi.mp4 sit inside the source?

Method: extract mono 8kHz WAV from the clip; slide it across the source's
audio (8kHz mono) comparing RMS-normalized 0.5s windows via cheap spectral
fingerprints (log-magnitude DFT of downmixed windows, top-K peak bins).
Coarse pass with 0.5s hops, refine with 1/30s steps around the best hit.
"""
import json
import subprocess
import numpy as np

CONTAINER_SRC = "/tmp/windwaker_src.mp4"
CLIP = "/app/clip1_hormozi.mp4"

def extract(path, out, ss=None, t=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-ac", "1",
           "-ar", "8000", "-f", "wav"]
    if ss is not None:
        cmd[2:2] = ["-ss", str(ss)]
    if t is not None:
        cmd[2:2] = ["-t", str(t)]
    cmd += ["-y", out]
    subprocess.run(cmd, check=True)
    return out

def load(path):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
                          "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], check=True,
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def peaks_spec(x, win=4000, hop=2000, k=8):
    """Fingerprint: for each hop, DFT magnitude -> top-k peak bin indices."""
    n = (len(x) - win) // hop + 1
    out = np.zeros((n, k), dtype=np.int32)
    for i in range(n):
        seg = x[i * hop:i * hop + win]
        if len(seg) < win:
            break
        spec = np.abs(np.fft.rfft(seg * np.hanning(win)))
        # peak bins (robust-ish): argsort top k, skip DC-heavy low bins under 50Hz
        spec[:4] = 0
        idx = np.argpartition(spec, -k)[-k:]
        out[i] = np.sort(idx)
    return out

def match():
    clip = load(CLIP)
    print("clip len:", len(clip) / 8000.0, "s")
    cspec = peaks_spec(clip)
    n_c = cspec.shape[0]

    # source: scan in 300s windows with 60s overlap (memory-friendly)
    dur_raw = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", CONTAINER_SRC], capture_output=True, text=True)
    dur = float(dur_raw.stdout.strip())
    print("source dur:", dur)

    best = (1e18, 0.0)
    W = 300.0
    pos = 0.0
    while pos < dur:
        t0 = max(0.0, pos - 60 if pos > 0 else 0)
        seg_path = f"/tmp/src_seg.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(max(0, pos)),
                        "-t", str(W), "-i", CONTAINER_SRC, "-ac", "1", "-ar", "8000",
                        "-f", "f32le", "-y", seg_path], check=True)
        src = np.frombuffer(open(seg_path, "rb").read() or b"", dtype=np.float32)
        if len(src) < len(clip):
            pos += W
            continue
        sspec = peaks_spec(src)
        n_s = sspec.shape[0]
        if n_s <= n_c:
            pos += W
            continue
        # coarse slide at 4-hop (2s) granularity
        for off in range(0, n_s - n_c, 4):
            d = np.sum(cspec != sspec[off:off + n_c])
            if d < best[0]:
                best = (d, pos + off * 0.25)
        pos += W - 60
    print("coarse best:", best)
    return best

def refine(coarse_off, span=6.0):
    """Fine slide: 0.25s window hops == 1 hop step. Scan +-6s at hop=1."""
    clip = load(CLIP)
    cspec = peaks_spec(clip)
    n_c = cspec.shape[0]
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", str(max(0, coarse_off - span)), "-t", str(50.6 + 2 * span),
                    "-i", CONTAINER_SRC, "-ac", "1", "-ar", "8000",
                    "-f", "f32le", "-y", "/tmp/src_fine.wav"], check=True)
    src = np.frombuffer(open("/tmp/src_fine.wav", "rb").read(), dtype=np.float32)
    sspec = peaks_spec(src)
    n_s = sspec.shape[0]
    base_t = max(0, coarse_off - span)
    best = (1e18, coarse_off)
    for off in range(0, max(1, n_s - n_c)):
        d = np.sum(cspec != sspec[off:off + n_c])
        if d < best[0]:
            best = (d, base_t + off * 0.25)
    return best

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        b = refine(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 3 else 6.0)
        print("REFINE best:", b)
        with open("/app/output/.match_result.json", "w") as f:
            json.dump({"fine_diff": int(b[0]), "offset": float(b[1])}, f)
        raise SystemExit(0)
    b = match()
    print("BEST_OFFSET_SECONDS", b)
    with open("/app/output/.match_result.json", "w") as f:
        json.dump({"coarse_diff": int(b[0]), "offset": float(b[1])}, f)