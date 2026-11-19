import json
t = json.load(open('/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json', encoding='utf-8'))
segs = t.get('segments', t if isinstance(t, list) else [])
print("SEGMENTS:", len(segs))
found = 0
for s in segs:
    txt = str(s.get('text', '')).lower()
    if any(k in txt for k in ('china', 'those happen', 'swindled', 'accept compensation', 'destroy', 'tomfoolery', 'richer')):
        print(f"{s.get('start'):8.2f}-{s.get('end'):8.2f}: {s.get('text')}")
        found += 1
print("FOUND:", found)