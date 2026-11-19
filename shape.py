import json
j = 'd51e9fc2-0c4f-432c-898c-35c679546474'
base = f'/app/output/{j}'
shorts = json.load(open(f'{base}/selected_clips.json', encoding='utf-8'))
if isinstance(shorts, dict):
    shorts = shorts.get('shorts', [])
s = shorts[0]
print('KEYS:', list(s.keys()))
print(json.dumps(s, indent=1)[:1500])