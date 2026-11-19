import json

import app

# Where does the in-memory job registry live / how is it persisted?
print("JOB_RETENTION_SECONDS:", app.JOB_RETENTION_SECONDS)

# Look at _job_view_from_disk and _recover_jobs_from_disk source
import inspect
print("=" * 40)
print(inspect.getsource(app._job_view_from_disk))