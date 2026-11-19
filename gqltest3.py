import json, urllib.request, urllib.error

GQL = "https://gql.twitch.tv/gql"
CID = "kimne78kx3ncx6brgbtobqbpkjuzhktq"
hdr = {"Client-ID": CID, "Content-Type": "application/json"}
op = {
    "operationName": "VideoMetadata",
    "variables": {"channelLogin": "", "videoID": "2901089887"},
    "extensions": {"persistedQuery": {
        "version": 1,
        "sha256Hash": "4511167eea7f753acc5a39181c7fe64cc1867c623531d00a49e6226a3633b974"}},
}
req = urllib.request.Request(GQL, data=json.dumps([op]).encode(), headers=hdr)
try:
    r = urllib.request.urlopen(req, timeout=30)
    print(r.status)
    d = json.loads(r.read().decode())
    v = d[0]["data"].get("video")
    print(json.dumps(v, indent=1)[:800] if v else d[0]["data"])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode()[:600])