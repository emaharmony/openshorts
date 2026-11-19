import glob
import json
import os
import time

import app

# Job 95708adc dir is gone. Check if any thumbnails for this job exist
thumb_dir = app.THUMBNAILS_DIR
print("THUMBNAILS_DIR:", thumb_dir)
thumbs = [f for f in os.listdir(thumb_dir) if "95708adc" in f or "1792037118" in f]
print("matching thumbnails:", thumbs[:20])

# Check the temp preview dirs etc
for pattern in ("*95708adc*", "*1792037118*"):
    hits = glob.glob(os.path.join(app.OUTPUT_DIR, pattern), recursive=False)
    print(pattern, "->", hits)