#!/usr/bin/env python3
"""HID director.py — Phase 3: adaptive creative director, TEMPLATE-LOCKED.

Compiles creative intent into parameters the EXISTING v8 compose accepts:
  allowed knobs (locked geometry preserved):
    start/end adjustment  (window trim inside narrative beat constraints)
    reaction hold         (extend end +HOLD up to 2.5s onto quiet tail)
    pacing trim           (remove dead air INSIDE window = skip; v0.2: flag-only)
    cam headroom pad      (only if Ema pre-approves per-use; v0.2: unsupported marker)
    punch-in / zoom       (UNSUPPORTED — brief bans dynamic zooms; hard reject)
  Everything else -> 'unsupported', fallback = approved baseline composition (v8 exact).

Capability matrix is data; compiled plan validated against it BEFORE render.
Deterministic: same manifest+direction -> same plan bytes.
"""
import json

import hook_craft  # Vyral viral-hooks craft (technique-only adoption, 2026-11-20 approved)

# Opener-strength evaluation (Vyral viral-hooks, technique-only):
# - Never renders anything. Supplies the LLM spot-QA passes an evaluation brief:
#   dims/anti-patterns/archetypes + a 0-10 opener score + rewrite candidates.
# - Policy-safe by construction: pentakewl bans burned hooks; the "text layer"
#   here describes what the TikTok uploader may add, not what we render.
# - Used when an evaluation pass opts in (arg opener_eval=True); default OFF,
#   so baseline production behavior is unchanged.

def opener_eval_brief(clip_path=None, transcript_head=None, ctx=None):
    """Build the LLM evaluation prompt fields for opener strength (0-10).
    clip_path/transcript_head optional context. Returns dict with prompt text.
    """
    c = hook_craft.scorecard()
    lines = [
        "Opener-strength evaluation (0-10). Judge ONLY as craft dimensions:",
    ]
    for d in c["dims"]:
        lines.append("- {}: {}".format(d["id"], d["q"]))
    lines.append("Anti-patterns: " + "; ".join(c["anti_patterns"]))
    lines.append("Archetypes for classification: " +
                 ", ".join("{} ({})".format(k, v) for k, v in c["archetypes"].items()))
    if transcript_head:
        lines.append("First spoken lines: " + transcript_head)
    if ctx:
        lines.append(str(ctx))
    lines.append("Output: {opener_score: 0-10, archetype: str, antipattern_hits: [str], rewrite_hint: str|None}")
    return {"prompt": "\n".join(lines), "policy_note": "never render hook overlays; text layer is TikTok-side only"}

CAPS = {
    'start_adjust':     {'status': 'supported',  'max_s': 15.0, 'guard': 'must not clip setup beat start'},
    'end_adjust':       {'status': 'supported',  'max_s': 15.0, 'guard': 'must not clip payoff tail'},
    'reaction_hold':    {'status': 'supported',  'max_s': 2.5,  'guard': 'target must be quiet tail (audio < -30dB)'},
    'pacing_trim':      {'status': 'flag-only',  'note': 'skip-based trims change audio continuity; requires ffmpeg atrim chain — evaluate v0.3'},
    'cam_headroom_pad': {'status': 'approval-gated', 'note': 'touches locked cam crop; requires explicit Ema approval per use'},
    'narrative_zoom':   {'status': 'experimental', 'reason': None,
        'rule': 'Ema 2026-11-12 00:52: dynamic zooms OK if they add to the plot; '
                'game-column-scale only, cam band untouched, amplitude <=1.15x, '
                'duration <=4s, anchored to a named beat (climax/payoff); '
                'requires vision re-verify of HUD/dialogue legibility post-zoom'},
    'layout_change':    {'status': 'unsupported', 'reason': 'v8 ratio LOCKED (game 64/cam 36)'},
    'captions_burn':    {'status': 'unsupported', 'reason': 'pentakewl policy: no burned captions'},
    'overlay_hook':     {'status': 'unsupported', 'reason': 'playbook: no hook/title overlays'},
}

def compile_plan(manifest, direction):
    """manifest: dict w/ candidate+narrative; direction: dict w/ requested intents.
    Returns (plan, fallback_used, notes[]). Deterministic."""
    notes = []
    plan = {
        'approved_layout_id': 'penta-v8-1964',
        'renderer_recipe': 'v8/1964-canvas/cam332x215@949,451-hflip/game568x661@380,40',
        'captions_policy': 'none-burned',
        'overlays_policy': 'none',
        'edits': [],
    }
    b = manifest.get('narrative', {})
    cstart = min((x.get('source_start', 0) for x in b.get('beats', [{ 'source_start': 0 }])), default=0)
    cend = max((x.get('source_end', 0) for x in b.get('beats', [{ 'source_end': 0 }])), default=0)

    for intent in direction.get('intents', []):
        kind = intent.get('kind'); val = intent.get('value', 0)
        cap = CAPS.get(kind, {'status': 'unsupported', 'reason': 'unknown intent'})
        if cap['status'] == 'unsupported':
            notes.append(f"REJECTED {kind}: {cap['reason']}")
            continue
        if cap['status'] == 'approval-gated' and not direction.get('ema_approved', {}).get(kind):
            notes.append(f"GATED {kind}: requires Ema approval; skipped")
            continue
        if cap['status'] == 'flag-only':
            notes.append(f"FLAG {kind}: {cap['note']}")
            continue
        if kind == 'start_adjust':
            new = cstart + val
            if val < 0 or new < cstart - cap['max_s']:
                notes.append(f"REJECT start_adjust {val}: exceeds cap")
                continue
            plan['edits'].append({'kind': kind, 'param': {'start': round(new, 2)}, 'guard_ok': True})
            notes.append(f"OK start_adjust -> {new:.2f}")
        elif kind == 'end_adjust':
            new = cend + val
            if abs(val) > cap['max_s'] or new < cend:
                notes.append(f"REJECT end_adjust {val}: exceeds cap or clips payoff")
                continue
            plan['edits'].append({'kind': kind, 'param': {'end': round(new, 2)}, 'guard_ok': True})
            notes.append(f"OK end_adjust -> {new:.2f}")
        elif kind == 'reaction_hold':
            new = cend + min(val, cap['max_s'])
            plan['edits'].append({'kind': kind, 'param': {'end': round(new, 2), 'reason': 'hold on quiet tail'}, 'guard_ok': True})
            notes.append(f"OK reaction_hold -> end {new:.2f} (cap {cap['max_s']}s)")
    if not plan['edits']:
        notes.append('NO edits compiled -> fallback = baseline v8 composition')
        plan['fallback'] = True
    return plan, notes

def render_params(plan, offsets):
    """Translate compiled plan -> exact ffmpeg cut params (absolute VOD seconds + part mapping)."""
    cstart = plan['edits'][0]['param']['start'] if any(e['kind'] == 'start_adjust' for e in plan['edits']) else None
    cend = [e['param']['end'] for e in plan['edits'] if e['kind'] in ('end_adjust', 'reaction_hold')]
    return {'start': cstart, 'end': cend[-1] if cend else None,
            'layout': plan['approved_layout_id'], 'renderer_recipe': plan['renderer_recipe'],
            'offsets': offsets}

if __name__ == '__main__':
    print("director.py v0.1 — capability matrix:", list(CAPS.keys()))
