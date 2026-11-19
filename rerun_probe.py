import json, urllib.request

d = json.loads(urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=15).read())
paths = sorted(d["paths"].keys())
for p in paths:
    if any(k in p for k in ("upload", "process", "jobs", "status", "videos")):
        print(p)
print("---")
# what method does /api/process take?
print({k: list(v.keys()) for k, v in d["paths"].items() if k in ("/api/process", "/api/uploads")})