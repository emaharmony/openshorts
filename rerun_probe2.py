import json, urllib.request

d = json.loads(urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=15).read())
for p in d["paths"]:
    if "process" in p or "status/{job_id}" in p or p == "/api/uploads/{upload_id}":
        for m in d["paths"][p]:
            print(m.upper(), p)
# find job status shape used by MCP get_job_status
import re
src = open("/app/mcp_server.py").read()
i = src.find("_tool_get_job_status")
print(src[i:i+700])