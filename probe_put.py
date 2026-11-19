import time, urllib.request, json

# 2MB body PUT to the upload slot -> does the server accept chunked bodies at all?
def req(method, path, body=None, timeout=60, ctype="application/json"):
    r = urllib.request.Request("http://localhost:8000" + path, data=body, method=method,
                               headers={"Content-Type": ctype})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, resp.read()
    except Exception as e:
        return getattr(e, 'code', 0), str(e)[:300]

st, up = req("POST", "/api/uploads", json.dumps({"filename": "probe.bin", "size": 2 * 1024 * 1024}).encode())
print("slot:", st, up)
if st == 200:
    d = json.loads(up)
    blob = b"x" * (2 * 1024 * 1024)
    st2, r2 = req("PUT", f"/api/uploads/{d['upload_id']}", blob, ctype="application/octet-stream", timeout=120)
    print("PUT 2MB:", st2, r2)