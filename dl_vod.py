import subprocess, time, os

OUTDIR = "/app/output/.vverify"
OUT = os.path.join(OUTDIR, "vod2901089887.%(ext)s")
URL = "https://www.twitch.tv/videos/2901089887"

LOG = "/app/output/.vverify/dl.log"
if os.path.exists("/app/output/.vverify/vod2901089887.mp4"):
    open(LOG, "w").write("already downloaded\n")
else:
    t0 = time.time()
    r = subprocess.run(
        ["python3", "-m", "yt_dlp", "-f", "mp4", "-o", OUT, "--no-part", URL],
        capture_output=True, text=True, timeout=5400)
    with open(LOG, "w") as f:
        f.write(r.stdout[-3000:] + "\nERR:\n" + r.stderr[-3000:])
        f.write("\nelapsed: %d rc: %d\n" % (time.time() - t0, r.returncode))