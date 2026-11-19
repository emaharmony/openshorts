#!/usr/bin/env python3
"""Second candidate pull: frames at 1768.2, 1738.8, 1838.2+ (re-pull since
C:\\temp_vverify was docker-cp'd before the LAST vverify run)."""
import subprocess, os
os.makedirs("/app/output/.vverify", exist_ok=True)
for c in (1768.2, 1738.8, 1650.0, 1660.0):
    t = c
    out = f"/app/output/.vverify/s2_{int(c*10)}.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", str(t), "-i", "/tmp/windwaker_src.mp4",
                    "-frames:v", "1", "-y", out], check=True)
    print(out, os.path.getsize(out))