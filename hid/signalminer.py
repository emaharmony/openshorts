#!/usr/bin/env python3
"""HID signalminer.py — Phase 1: cheap full-VOD signal extraction, no vision calls.

Per 50s window (absolute VOD seconds):
  transcript: chars/s, words, snippet
  audio:      peak M (ebur128 momentary), mean M, silence_ratio, loud_jumps (>=12dB rises to >=-25dB)
  video:      scene-cut count + max scene score (single-pass select@fps=4)
Missing/bad audio (digital -91dB head of part A) -> audio_unavailable=true, NOT negative evidence.

Output: hid/baseline/signals.json  {"vod_id":..., "windows":[{win globals...}]}
Offset rule: part B local = global - 5130 (asserted, never assumed — G-9).
"""
import os
import json, subprocess, re, os, sys

W = os.environ.get('HID_WORK', os.path.dirname(os.path.abspath(__file__)))
HID = os.path.dirname(os.path.abspath(__file__))
PARTS = {'A': (f'{W}/nw_a.mp4', 0.0), 'B': (f'{W}/nw_b.mp4', 5130.0)}
VOD_END = 10259.96
WIN = 50.0

def part_for(g):
    if g < 5130.0: return 'A'
    return 'B'

def local_of(g):
    return g - PARTS[part_for(g)][1]

def ebur128_series_global():
    """Single pass per part over the WHOLE file; returns list[(global_t, M_db)]."""
    out = []
    for pid, (src, off) in PARTS.items():
        if not os.path.exists(src):
            raise RuntimeError(f"missing source {src}")
        dur_probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
                                    '-of','csv=p=0',src], capture_output=True, text=True)
        dur = float(dur_probe.stdout.strip())
        r = subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',src,
                            '-filter_complex','ebur128','-f','null','-'],
                           capture_output=True, text=True, timeout=3600)
        for line in r.stderr.splitlines():
            m = re.search(r't:\s*([\d.]+)\s+TARGET:-23 LUFS\s+M:\s*(-?[\d.]+)\s+S:', line)
            if m:
                lt, mv = float(m.group(1)), float(m.group(2))
                g = lt + off
                if g <= VOD_END - 30:
                    out.append((g, mv))
        print(f"ebur128 part {pid}: {dur:.0f}s scanned", flush=True)
    out.sort()
    return out

def scene_events_global(thresh=0.06):
    """Single pass per part at fps=4: scene-score events w/ global timestamps."""
    ev = []
    for pid, (src, off) in PARTS.items():
        r = subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',src,
                            '-vf', f"fps=4,select=gt(scene\\,{thresh}),metadata=print:file=-",
                            '-f','null','-'],
                           capture_output=True, text=True, timeout=3600)
        # metadata prints go to stdout (file=-) as key/value blocks
        cur_t = None
        for line in (r.stdout or '').splitlines():
            km = re.match(r'frame:(\d+)\s+pts:\d+\s+pts_time:([\d.]+)', line)
            if km:
                cur_t = float(km.group(2)) + off
                continue
            sm = re.match(r'lavfi\.scene_score=([\d.]+)', line)
            if sm and cur_t is not None:
                ev.append((cur_t, float(sm.group(1))))
        print(f"scene pass part {pid}: {len(ev)} events so far (thr {thresh})", flush=True)
    ev.sort()
    return ev

def transcript_windows():
    sa = json.load(open(f'{W}/nw_meta_a.json'))['transcript']['segments']
    sb = json.load(open(f'{W}/nw_meta_b.json'))['transcript']['segments']
    segs = [(s['start'], s['end'], s['text']) for s in sa]
    segs += [(s['start'] + 5130.0, s['end'] + 5130.0, s['text']) for s in sb]
    segs.sort()
    return segs

def main():
    n_windows = int(VOD_END // WIN)
    series = ebur128_series_global()
    cuts = scene_events_global()
    segs = transcript_windows()

    windows = []
    for w in range(n_windows):
        t0, t1 = w * WIN, (w + 1) * WIN
        rec = {'g_start': round(t0, 1), 'g_end': round(t1, 1)}

        # --- audio ---
        vals = [m for (g, m) in series if t0 <= g < t1]
        if vals:
            live = [v for v in vals if v > -85.0]
            if not live:
                rec['audio_unavailable'] = True   # digital silence region (head of part A)
            else:
                rec['peak_db'] = round(max(live), 1)
                rec['mean_db'] = round(sum(live) / len(live), 1)
                rec['silence_ratio'] = round(sum(1 for v in vals if v <= -60.0) / len(vals), 3)
                jumps = 0
                for i in range(1, len(vals)):
                    if vals[i] - vals[i-1] >= 12.0 and vals[i] >= -25.0:
                        jumps += 1
                rec['loud_jumps'] = jumps
        else:
            rec['audio_unavailable'] = True

        # --- video ---
        cev = [s for (g, s) in cuts if t0 <= g < t1]
        rec['scene_cuts'] = len(cev)
        rec['scene_max'] = round(max(cev), 3) if cev else 0.0

        # --- transcript ---
        chars = 0.0; words = 0; snips = []
        for st, en, txt in segs:
            ov = max(0.0, min(en, t1) - max(st, t0))
            if ov > 0:
                span = max(0.1, en - st)
                chars += len(txt) * ov / span
                words += len(txt.split()) * ov / span
                if ov > 0.5 * span or (en - st) < 3:
                    snips.append(txt.strip())
        rec['chars_per_s'] = round(chars / WIN, 2)
        rec['words'] = int(words)
        rec['snippet'] = ' | '.join(snips)[:220]
        windows.append(rec)

    os.makedirs(f'{HID}/baseline', exist_ok=True)
    out = {'vod_id': '2923641711', 'win_seconds': WIN,
           'offsets': {'partA': 0.0, 'partB': 5130.0}, 'windows': windows}
    json.dump(out, open(f'{HID}/baseline/signals.json', 'w'), indent=1)
    print(f"signals.json written: {len(windows)} windows; "
          f"audio-unavail={sum(1 for r in windows if r.get('audio_unavailable'))}, "
          f"windows w/ peak={sum(1 for r in windows if 'peak_db' in r)}")

if __name__ == '__main__':
    main()
