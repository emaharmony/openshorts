import json
import os

OUT = "/app/output"

for job_id in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, job_id)
    if not os.path.isdir(p) or job_id == "thumbnails":
        continue
    metas = [f for f in os.listdir(p) if f.endswith("_metadata.json")]
    for mf in metas:
        try:
            with open(os.path.join(p, mf)) as f:
                data = json.load(f)
        except Exception as e:
            print(f"{job_id}: BAD {e}")
            continue
        src = data.get("source_video", "?")
        print(f"\n=== {job_id} ({src}) ===")
        for i, s in enumerate(data.get("shorts", [])):
            print(f"  clip {i + 1}: {s.get('start')} - {s.get('end')} | {s.get('title', s.get('video_title_for_youtube_short', '(no title)'))}")