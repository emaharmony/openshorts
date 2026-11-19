import json, glob
for j in ('a206ecdd-9950-4790-8128-fe34eaf9b6fc', 'c825976c-5d61-4fb7-a4eb-aacab04d114c', 'd51e9fc2-0c4f-432c-898c-35c679546474', 'f4cb9220-3be7-49aa-8c1c-cfaab1e0d8a9'):
    base = f'/app/output/{j}'
    print('=' * 16, j[:8])
    shorts = json.load(open(f'{base}/selected_clips.json', encoding='utf-8'))
    if isinstance(shorts, dict):
        shorts = shorts.get('shorts', [])
    for i, s in enumerate(shorts, 1):
        print(f"  clip_{i}: {s.get('start'):8.2f}-{s.get('end'):8.2f}  {s.get('title')}")
    for m in glob.glob(f'{base}/*metadata*.json'):
        md = json.load(open(m, encoding='utf-8'))
        sh = md.get('shorts', [])
        print(f"  meta shorts: {len(sh)} | first: {sh[0].get('start') if sh else None}-{sh[0].get('end') if sh else None}")