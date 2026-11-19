import json
import os

import app

# Check all output dirs on disk and their mtimes vs retention
now = __import__("time").time()
for job_id in sorted(os.listdir(app.OUTPUT_DIR)):
    job_path = os.path.join(app.OUTPUT_DIR, job_id)
    if not os.path.isdir(job_path):
        continue
    mtime = os.path.getmtime(job_path)
    age_days = (now - mtime) / 86400
    retention_days = app.JOB_RETENTION_SECONDS / 86400
    print(f"{job_id}: age={age_days:.2f}d retention={retention_days:.2f}d "
          f"expired={age_days > retention_days}")