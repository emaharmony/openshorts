import json

p = "/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json"
with open(p) as f:
    data = json.load(f)
segs = data if isinstance(data, list) else data.get("segments", data.get("lines", []))
print("segments:", len(segs), "| language:", data.get("language") if isinstance(data, dict) else "?")
last = segs[-1]
print("last end:", last.get("end"))

terms = ["bone", "china", "compensat", "unhinged", "rupee", "242", "vase", "pay me", "pay for", "priceless"]
for s in segs:
    txt = (s.get("text") or "").lower()
    if any(t in txt for t in terms):
        mark = " <<< " + ",".join(t for t in terms if t in txt)
        print(f"{s.get('start',0):9.2f}-{s.get('end',0):9.2f}  {(s.get('text') or '')[:130]}{mark[:60]}")