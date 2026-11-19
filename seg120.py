import json
t = json.load(open('/app/output/2318fd8a-c0ca-442a-b0c9-dd49f5634d75/source_transcript.json', encoding='utf-8'))
segs = t.get('segments', t if isinstance(t, list) else [])
for s in segs:
    st = float(s.get('start', 0))
    if 120 < st < 350:
        print('%8.2f-%8.2f: %s' % (st, s.get('end', 0), s.get('text')))