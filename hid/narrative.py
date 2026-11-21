#!/usr/bin/env python3
"""HID narrative.py — Phase 2: beat tagging, validation, narrative boundary selection.

Editorial concepts (generic storytelling craft, implemented from scratch — no third-party
code copied; brief §6): beats, cold-viewer test, reaction-room boundaries.

BEAT_TYPES: opener|setup|comedy|escalation|climax|reaction|payoff|resolution
Beat record: {type, source_start, source_end, evidence_refs[...], confidence, note}
Validation: ordered, non-negative spans, inside padded window, every beat has >=1 evidence ref.

Boundary selector rules (deterministic):
  R1 start snaps to a transcript gap >= 1.0s (breath) at/after narrative start minus slack
  R2 end = payoff beat end + REACTION_TAIL (default 1.4s), never before climax end
  R3 do not include trailing segments that open NEW unresolved tension (heuristic:
     segment starting <1.2s after payoff end and containing question/failure markers
     pushes end back to payoff end + tail)
  R4 durations clamped [MIN_DUR, MAX_DUR] via staging note, not silent truncation
"""
import json

BEAT_TYPES = {'opener','setup','comedy','escalation','climax','reaction','payoff','resolution'}
REACTION_TAIL = 1.4
MIN_DUR, MAX_DUR = 40.0, 115.0
NEW_TENSION_MARKERS = ("oh no", "no, she", "i can't continue", "what the", "why does")

def validate_beats(beats, lo, hi):
    errs = []
    last = -1e9
    for i, b in enumerate(beats):
        if b.get('type') not in BEAT_TYPES: errs.append(f"beat{i}: bad type {b.get('type')}")
        s, e = b.get('source_start', -1), b.get('source_end', -1)
        if not (lo <= s < e <= hi + 0.01): errs.append(f"beat{i}: span {s}-{e} outside window {lo}-{hi}")
        if s < last: errs.append(f"beat{i}: starts before previous beat ends (unsorted/overlap)")
        last = max(last, e)
        if not b.get('evidence_refs'): errs.append(f"beat{i}: no evidence_refs")
    return errs

def select_boundary(segments, beats, opts=None):
    """segments: [(start,end,text)] around the window; beats: validated list.
    Returns dict with snapped start/end + rationale strings."""
    o = {'reaction_tail': REACTION_TAIL, 'start_slack': 3.0}
    if opts: o.update(opts)
    rationales = []
    # narrative start = first beat start
    b0 = beats[0]
    start = b0['source_start']
    # R1: snap to a breath gap in [start-o.start_slack, start]
    gaps = []
    for i in range(1, len(segments)):
        gap = segments[i][0] - segments[i-1][1]
        if gap >= 1.0:
            gaps.append((segments[i][0], gap))
    lo_s, hi_s = start - o['start_slack'], start
    cands = [t for (t, g) in gaps if lo_s <= t <= hi_s]
    if cands:
        start = cands[0]
        rationales.append(f"R1: start snapped to breath gap at {start:.2f}")
    else:
        rationales.append(f"R1: no breath gap within slack; kept {start:.2f} (mid-stream risk flagged)")
    # R2: end after payoff/climax
    anchor = max(beats[-1]['source_end'], beats[-2]['source_end'] if len(beats) > 1 else 0)
    end = anchor + o['reaction_tail']
    rationales.append(f"R2: end = last critical beat end {anchor:.2f} + {o['reaction_tail']}s reaction tail")
    # R3: trailing new-tension segments -> pull back
    pulled = False
    for (st, en, tx) in segments:
        if st > anchor and st < anchor + 1.2:
            if any(m in tx.lower() for m in NEW_TENSION_MARKERS):
                pulled = True
                break
    if pulled:
        end = anchor + o['reaction_tail']
        rationales.append("R3: trailing segment opens new tension; end held at payoff tail")
    dur = end - start
    if dur < MIN_DUR: rationales.append(f"R4: duration {dur:.1f}s < MIN {MIN_DUR} — needs context growth (flag)")
    if dur > MAX_DUR: rationales.append(f"R4: duration {dur:.1f}s > MAX {MAX_DUR} — split or tighten (flag)")
    return {'start': round(start, 2), 'end': round(end, 2), 'dur': round(dur, 2),
            'rationales': rationales}

def cold_viewer_check(beats):
    """Returns (ok, missing) — cold viewer needs: setup or opener context, a climax, a payoff."""
    types = {b['type'] for b in beats}
    missing = []
    if not (types & {'opener', 'setup'}): missing.append('setup/opener')
    if not (types & {'climax', 'escalation'}): missing.append('climax/escalation')
    if not (types & {'payoff', 'reaction', 'resolution'}): missing.append('payoff/resolution')
    return (not missing, missing)

if __name__ == '__main__':
    print("narrative.py v0.1 — import from prototypes; beat data tagged by Lumi with evidence refs")
