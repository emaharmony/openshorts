import json
for j in ('a206ecdd-9950-4790-8128-fe34eaf9b6fc', 'c825976c-5d61-4fb7-a4eb-aacab04d114c', 'd51e9fc2-0c4f-432c-898c-35c679546474', 'f4cb9220-3be7-49aa-8c1c-cfaab1e0d8a9'):
    base = f'/app/output/{j}'
    print('=' * 20, j[:8])
    try:
        sc = json.load(open(f'{base}/selected_clips.json', encoding='utf-8'))
        shorts = sc.get('shorts', sc if isinstance(sc, list) else [])
        for i, s in enumerate(shorts[:3], 1):
            seg = s.get('segments', [{}])[0]
            print(f"  clip_{i}: {seg.get('start')}-{seg.get('end')} | {str(s.get('title'))[:60]}")
    except Exception as e:
        print('  sc err:', e)
    try:
        md = json.load(open(f'{base}/{j}_metadata.json', encoding='utf-8'))
        sv = md.get('source_video')
        if isinstance(sv, dict):
            sv = sv.get('name') or sv.get('filename')
        print('  meta source_video:', sv)
        shorts2 = md.get('shorts', [])
        if shorts2:
            seg2 = shorts2[0].get('segments', [{}])[0]
            print(f"  meta clip_1: {seg2.get('start')}-{seg2.get('end')}")
    except Exception as e:
        print('  md err:', e)