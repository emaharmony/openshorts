import subprocess

out = subprocess.run(
    ["grep", "-rn", "selected_clips", "/app/main.py", "/app/app.py"],
    capture_output=True, text=True,
).stdout
# keep it short
lines = [l for l in out.splitlines() if "selected_clips" in l]
for l in lines[:15]:
    print(l[:200])

print("=====HOOK BURN=====")
out2 = subprocess.run(
    ["grep", "-n", "viral_hook_text", "/app/main.py"],
    capture_output=True, text=True,
).stdout
for l in out2.splitlines()[:15]:
    print(l[:200])