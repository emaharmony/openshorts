#!/usr/bin/env python3
import json
t = json.load(open('/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json', encoding='utf-8'))
segs = t.get('segments', t if isinstance(t, list) else [])
for s in segs:
    st = float(s.get('start', 0))
    if 1560 < st < 1880:
        print(f"{st:7.1f}-{float(s.get('end',0)):7.1f}: {s.get('text')}")