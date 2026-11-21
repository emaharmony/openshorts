#!/usr/bin/env python3
"""HID candidate_ranker.py — Phase 1: coarse-signal flagging -> focused candidate list.

Cheap-signal scorer (NO vision, NO LLM):
  transcript: chars_per_s percentile (density = signal but not sole gate)
  audio: peak_db percentile, loud_jumps, silence_ratio penalty
  video: scene_cuts percentile (action/variety)
  quips: LOW speech + HIGH loud_jumps/peak + no existing pick nearby = whisper-comedy candidate
  suspense: LOW speech + HIGH scene_max with low cuts = atmosphere beat

Output: hid/baseline/candidates.json — top N candidates with evidence + rationale strings.
Guarantee: each candidate record carries signals dict + rationale; nothing requires vision.
"""
import os
import json, os, sys

HID = os.path.dirname(os.path.abspath(__file__))
WIN = 50.0
EXISTING_PICKS = [740, 1830, 1610, 2420, 1090, 5410, 5860, 5630, 5290, 5980]  # F-batch, global starts
MIN_SEP_MIN = 2.5      # min separation between NEW candidates
MIN_SEP_EXISTING = 1.5 # min separation from existing F picks (dedupe guard)

def percentile(pct, vals):
    vals = sorted(vals)
    k = (len(vals) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[f] + (vals[c] - vals[f]) * (k - f)

def main():
    topn = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    data = json.load(open(f'{HID}/baseline/signals.json'))
    wins = data['windows']

    # build percentile tables over usable audio windows
    usable = [w for w in wins if not w.get('audio_unavailable')]
    for key in ('chars_per_s', 'peak_db', 'scene_cuts', 'scene_max', 'silence_ratio'):
        vals = [w.get(key, 0) for w in usable]
        for w in wins:
            w['pct_' + key] = round(sum(1 for v in vals if v <= w.get(key, 0)) / len(vals), 3)

    cands = []
    for w in wins:
        g = w['g_start']
        if g < 120 or g > 10100:
            continue
        if any(abs(g - p) < MIN_SEP_EXISTING * 60 for p in EXISTING_PICKS):
            w['tag'] = 'near-existing-pick'
            continue
        if w.get('audio_unavailable'):
            w['tag'] = 'audio-unavailable'
            continue

        speech = w['pct_chars_per_s']
        energy = w['pct_peak_db']
        cuts = w['pct_scene_cuts']
        jumps = w.get('loud_jumps', 0)
        quiet = 1.0 - speech

        # composite cheap score (transcript is ONE voice among several now)
        score = (0.30 * speech + 0.25 * energy + 0.20 * cuts
                 + 0.15 * (1.0 - w['pct_silence_ratio']) + 0.10 * min(1.0, jumps / 6.0))

        rationale = []
        if speech >= 0.7: rationale.append('dense dialogue')
        if energy >= 0.8: rationale.append(f"loud peak {w.get('peak_db')}dB")
        if jumps >= 3: rationale.append(f'{jumps} loud-jump moments (reactions?)')
        if cuts >= 0.8: rationale.append(f"high visual variety ({w['scene_cuts']} scene events)")

        # --- low-speech profile: quiet-but-structured beats (Phase 1 recall target) ---
        # dialogue giants peak near 0dB (laughter/shouting); whisper bits sit -24..-36dB BY DESIGN.
        # discriminating features: moderate words (25-46), near-zero silence_ratio (audio active), scene cuts (game events).
        peak = w.get('peak_db', -99.0)
        silr = w['pct_silence_ratio']
        low_sp = speech <= 0.3
        if low_sp and cuts >= 0.7 and silr <= 0.3 and 20 <= w.get('words', 0) <= 50 and -36 <= peak <= -22:
            score += 0.16
            rationale.append('WHISPER-BIT: low speech + active audio + game events (quiet comedy/suspense candidate)')
        elif low_sp and w['pct_scene_max'] >= 0.75 and cuts <= 0.4:
            score += 0.08
            rationale.append('atmosphere beat: sparse speech, big scene change')

        cands.append({'g_start': g, 'g_end': g + WIN, 'score': round(score, 3),
                      'signals': {k: w.get(k) for k in
                                  ('chars_per_s', 'words', 'peak_db', 'mean_db', 'silence_ratio',
                                   'loud_jumps', 'scene_cuts', 'scene_max',
                                   'pct_chars_per_s', 'pct_peak_db', 'pct_scene_cuts')},
                      'rationale': rationale or ['weak aggregate'],
                      'snippet': w.get('snippet', '')})

    # diversity separation
    cands.sort(key=lambda c: -c['score'])
    picked = []
    for c in cands:
        if all(abs(c['g_start'] - p['g_start']) >= MIN_SEP_MIN * 60 for p in picked):
            picked.append(c)
        if len(picked) >= topn:
            break

    out = {'vod_id': data['vod_id'], 'method': 'cheap-signals v0.1',
           'excluded_near_existing': sum(1 for w in wins if w.get('tag') == 'near-existing-pick'),
           'audio_unavailable_windows': sum(1 for w in wins if w.get('tag') == 'audio-unavailable'),
           'candidates': picked}
    json.dump(out, open(f'{HID}/baseline/candidates.json', 'w'), indent=1)
    print(f"{len(picked)} candidates (from {len(cands)} scored windows):")
    for c in picked:
        print(f"  {c['g_start']:>6.0f}s score={c['score']:<5} {', '.join(c['rationale'])[:90]}")

if __name__ == '__main__':
    main()
