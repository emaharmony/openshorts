import json

p = "/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json"
with open(p) as f:
    data = json.load(f)
segs = data if isinstance(data, list) else data.get("segments", data.get("lines", []))
# print all segments 60-260s to see the whole vase scene context
for s in segs:
    st = s.get("start", 0)
    if st < 55:
        continue
    if st > 270:
        break
    print(f"{s.get('start', 0):8.2f} - {s.get('end', 0):8.2f}  {(s.get('text') or '')[:150]}")