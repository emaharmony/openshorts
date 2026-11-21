#!/usr/bin/env python3
"""chatminer.py — chat-signal extraction from TwitchDownloader JSON (TwitchDownloaderCLI chatdownload).

Signals per bucket (default 15s): unique-user rate, emote-burst mass, burst intensity,
question/fail markers, streamer-shoutouts. Graceful-absent: returns {"available": False,...} when
the file has < MIN_COMMENTS. Chat = supporting evidence only (task §3): never sole proof.
Output: {"available": bool, "volid": str, "comments": int, "buckets": [...], "summary": {...}}
"""
import json, re, collections

BUCKET_S = 15.0
MIN_COMMENTS = 200
EMOTE_FALLBACK = re.compile(r'\b(KEKW|POG|POGGERS|LUL|LULW|OMEGALUL|Clap|EZ|PogChamp|PepeLaugh|Sadge|WOW|HAHA|HACKER|GOTTEM|CLAP|AYO|WHAT|NO+|W+|LETS+GO|GG)\b', re.I)
QUESTION = re.compile(r'\?')
FAIL = re.compile(r'\b(rip|oof|f in chat|broke|died|failed|gone|lost|ded)\b', re.I)
BOTS = {'streamelements','nightbot','moobot','streamlabs','fossabot','wizebot','venobot','pentakewl'}

def available(path):
    try:
        d = json.load(open(path))
        return len(d.get('comments') or []) >= MIN_COMMENTS
    except Exception:
        return False

def mine(path):
    d = json.load(open(path))
    comments = [c for c in (d.get('comments') or []) if (c.get('commenter') or {}).get('name','').lower() not in BOTS]
    if len(comments) < MIN_COMMENTS:
        return {"available": False, "volid": str((d.get('video') or {}).get('id')), "comments": len(comments),
                "reason": "sparse chat (<%d non-bot comments) — chat channel disabled for this VOD" % MIN_COMMENTS}
    buckets = collections.defaultdict(lambda: {"users": set(), "n": 0, "emotes": 0, "q": 0, "fail": 0, "texts": []})
    for c in comments:
        t = float(c.get('content_offset_seconds') or 0)
        b = buckets[int(t // BUCKET_S)]
        who = (c.get('commenter') or {}).get('name') or c.get('_id')
        b["users"].add(who); b["n"] += 1
        frags = (c.get('message') or {}).get('fragments') or []
        text = "".join(f.get('text','') for f in frags)
        b["emotes"] += len(EMOTE_FALLBACK.findall(text))
        b["q"] += bool(QUESTION.search(text))
        b["fail"] += bool(FAIL.search(text))
        if len(b["texts"]) < 3: b["texts"].append(text[:60])
    out = []
    for k in sorted(buckets):
        b = buckets[k]
        out.append({"t0": k*BUCKET_S, "t1": (k+1)*BUCKET_S, "rate": b["n"]/BUCKET_S, "users": len(b["users"]),
                    "emotes": b["emotes"], "q": b["q"], "fail": b["fail"], "sample": b["texts"]})
    n = len(comments)
    summary = {"comments": n, "span_s": out[-1]["t0"] if out else 0,
               "hottest": sorted(out, key=lambda b: b["rate"], reverse=True)[:5],
               "emote_bursts": [b for b in sorted(out, key=lambda b: b["emotes"], reverse=True) if b["emotes"]>0][:5],
               "question_buckets": sum(1 for b in out if b["q"]>0)}
    return {"available": True, "volid": str((d.get('video') or {}).get('id')), "comments": n,
            "bucket_s": BUCKET_S, "buckets": out, "summary": summary}

if __name__ == "__main__":
    import sys
    r = mine(sys.argv[1])
    json.dump(r, open(sys.argv[2], "w"), indent=1)
    print(json.dumps({"available": r["available"], "comments": r.get("comments", 0), "reason": r.get("reason")}, ensure_ascii=False))
