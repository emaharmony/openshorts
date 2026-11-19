import json
import os
import glob

# Find a Windwaker transcript on disk (job 2318fd8a has source_transcript.json)
# and locate the vase scene ~0-60s: "bone-china vases" / "10 Rupees" / vase breaking.
p = "/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json"
with open(p) as f:
    data = json.load(f)
segs = data if isinstance(data, list) else data.get("segments", data.get("lines", []))
print("total segments:", len(segs))

# scan 0-140s for 'vase' mentions
hits = []
for s in segs:
    st = s.get("start", 0)
    if st > 200:
        break
    txt = (s.get("text") or "")
    if "vase" in txt.lower() or "rupee" in txt.lower():
        hits.append((st, s.get("end"), txt))
for st, en, txt in hits:
    print(f"{st:8.2f} - {en:8.2f}  {txt[:120]}")