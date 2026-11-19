import json, urllib.request

GQL = "https://gql.twitch.tv/gql"
Q = {"query": "{video(id:\"2901089887\"){id,title,lengthSeconds,viewCount,broadcastType,owner{login}}}"}
hdr = {"Client-ID": "kimne78kx3ncxokai9c6oz4nkt5awg",
       "Content-Type": "application/json"}
r = urllib.request.urlopen(urllib.request.Request(
    GQL, data=json.dumps(Q).encode(), headers=hdr), timeout=30)
print(r.status, r.read().decode()[:500])