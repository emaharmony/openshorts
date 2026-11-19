import json, urllib.request

BASE = "http://localhost:8000"

def mcp_tool(name, args, id=1):
    payload = {"jsonrpc": "2.0", "id": id, "method": "tools/call",
               "params": {"name": name, "arguments": args}}
    req = urllib.request.Request(BASE + "/mcp",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    r = urllib.request.urlopen(req, timeout=120)
    raw = r.read().decode()
    # SSE or plain JSON
    if raw.startswith("{"):
        d = json.loads(raw)
    else:
        # take last data: line
        d = json.loads([l for l in raw.splitlines() if l.startswith("data:")][-1][5:])
    return d

def rest(method, path, body=None, timeout=120):
    req = urllib.request.Request(BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        return e.code, body

# 1) create upload slot
st, up = rest("POST", "/api/uploads", {"filename": "Windwaker_playthrough!_(first_time_D).mp4", "size": 4490827916})
print("upload slot:", st, up)