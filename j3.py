import json

import app

# The 95708adc job dir was purged from disk; can we find WHAT source URL it used?
# Check the memory of the running app for publish_jobs / saas_jobs that mention the id
for reg_name in ("jobs", "saas_jobs"):
    reg = getattr(app, reg_name, {})
    print(reg_name, "->", list(reg.keys())[:20])

# Any archived managed jobs in the cloud db?
try:
    from cloud.database import db  # type: ignore

    print("cloud db available")
except Exception as e:
    print("cloud db not available:", e)