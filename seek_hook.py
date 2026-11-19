"""Search the WINDWAKER source transcript 2318fd8a for the hook lines.
Print every segment containing key words, with exact indices."""
import json, re

t = json.load(open('/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json', encoding='utf-8'))
segs = t.get('segments', t if isinstance(t, list) else [])
kws = ['china', 'happen', 'swindle', 'compensat', 'tomfool', 'richer', 'vase', 'rupee', 'narcissist']
for i, s in enumerate(segs):
    txt = str(s.get('text', '')).lower()
    if any(k in txt for k in kws):
        print(f"[{i:3d}] {s.get('start'):8.2f}-{s.get('end'):8.2f}: {s.get('text')}")
print("---done")