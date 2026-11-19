#!/usr/bin/env python3
"""Vision-verify: extract clip t=20s frame + source frames at candidate+20s,
pull back as jpgs for LLM-vision comparison."""
import subprocess, os

os.makedirs("/app/output/.vverify", exist_ok=True)

# clip t=20s
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "/app/clip1_hormozi.mp4",
                "-ss", "20", "-frames:v", "1", "-y", "/app/output/.vverify/clip_t20.jpg"], check=True)

cands = [1695.5, 1696.2, 1701.4, 1735.4, 1758.7, 1771.8, 1829.8, 1838.2, 1848.9, 6146.2]
for c in cands:
    t = c + 20.0
    out = f"/app/output/.vverify/src_{int(c*10)}.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", str(t), "-i", "/tmp/windwaker_src.mp4",
                    "-frames:v", "1", "-y", out], check=True)
print("done")
for f in sorted(os.listdir("/app/output/.vverify")):
    print(f, os.path.getsize(f"/app/output/.vverify/{f}"))