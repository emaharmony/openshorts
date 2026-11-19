import inspect

import app

print(inspect.getsource(app._job_source_url))
print("=" * 60)
src = inspect.getsource(app)
# find the delete/purge endpoints
import re

for m in re.finditer(r"def (delete_\w+|purge_\w+|remove_\w+)\(.*?\):", src):
    print("ENDPOINTish:", m.group(1))