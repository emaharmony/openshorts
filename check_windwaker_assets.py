import json
import os

jobs = [
    "2318fd8a-c0ca-442a-b0c9-dd49f5634d75",
    "a206ecdd-9950-4790-8128-fe34eaf9b6fc",
    "c825976c-5d61-4fb7-a4eb-aacab04d114c",
    "d51e9fc2-0c4f-432c-898c-35c679546474",
    "f4cb9220-3be7-49aa-8c1c-cfaab1e0d8a9",
]
for j in jobs:
    p = os.path.join("/app/output", j)
    fs = os.listdir(p)
    vids = [f for f in fs if f.endswith(".mp4")]
    print(j[:8], "| files:", len(fs), "| mp4:", vids[:3] if vids else "NONE")
print("uploads:", [f for f in os.listdir("/app/uploads") if "indwaker" in f])