#!/usr/bin/env python3
"""Whole-word caption scan of clip1_final_style.mp4: extract 1 frame per
second (0-50s), tile 4x13 grid with time labels burned in, ONE vision call."""
import subprocess, os

os.makedirs("/app/output/.capscan", exist_ok=True)
# Remove old frames
for f in os.listdir("/app/output/.capscan"):
    os.remove(f"/app/output/.capscan/{f}")

for sec in range(0, 51):
    out = f"/app/output/.capscan/f{sec:02d}.jpg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-ss", str(sec), "-i", "/app/clip1_hormozi.mp4",
                    "-frames:v", "1", "-vf", "scale=270:480",
                    "-y", out], check=True)

# Build mosaic with IM if available, else PIL
try:
    from PIL import Image, ImageDraw
    cols, rows = 9, 6
    W, H = 270, 480
    LBL = 24
    mosaic = Image.new("RGB", (cols * (W + 4), rows * (H + LBL + 4)), (18, 18, 18))
    d = ImageDraw.Draw(mosaic)
    for i in range(rows * cols):
        sec = i
        if sec > 50:
            break
        p = f"/app/output/.capscan/f{sec:02d}.jpg"
        if not os.path.exists(p):
            continue
        x = (i % cols) * (W + 4)
        y = (i // cols) * (H + LBL + 4)
        d.text((x + 6, y + 4), f"t={sec}s", fill=(255, 220, 0))
        img = Image.open(p)
        mosaic.paste(img, (x, y + LBL))
    mosaic.save("/app/output/.vverify/capscan_mosaic.jpg", quality=82)
    print("mosaic saved", mosaic.size)
except Exception as e:
    print("PIL fail:", e)