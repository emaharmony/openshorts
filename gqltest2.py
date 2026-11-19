import json, urllib.request, urllib.error

GQL = "https://gql.twitch.tv/gql"
Q = {"query": '{video(id:"2901089887"){id,title,lengthSeconds,viewCount,broadcastType,owner{login}}}'}
hdr = {"Client-ID": "kimne78kx3ncxokai9c6oz4nkt5awg",
       "Content-Type": "application/json"}
req = urllib.request.Request(GQL, data=json.dumps(Q).encode(), headers=hdr)
try:
    r = urllib.request.urlopen(req, timeout=30)
    print(r.status, r.read().decode()[:600])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode()[:600])