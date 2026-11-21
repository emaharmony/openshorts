#!/usr/bin/env python3
"""HID rollout.py — Phase 5: feature-flag policy + rollback switch.

Flag file: hid/FLAG.json  {"mode": "baseline"|"shadow"|"active", "since": iso, "by": "..."}
  baseline: production scripts run exactly as before (hid/ exists but is inert)
  shadow:   new pipeline RUNS and writes hid/ outputs + reports, but production
            uses baseline picks; diffs reported per batch (no prod artifacts)
  active:   new pipeline's candidates/manifests become production input
Rollback = set mode back to baseline (one write); no geometry/scripts revert needed.
"""
import os
import json, os, datetime, subprocess

HID=os.path.dirname(os.path.abspath(__file__))
FLAG=f'{HID}/FLAG.json'

def get():
    if os.path.exists(FLAG): return json.load(open(FLAG))
    return {'mode':'baseline','since':None,'by':'default'}

def set_mode(mode, by='Lumi'):
    assert mode in ('baseline','shadow','active')
    j={'mode':mode,'since':datetime.datetime.now().isoformat(),'by':by}
    json.dump(j, open(FLAG,'w'), indent=1)
    return j

def guarded_active(ema_ok):
    """Going 'active' requires explicit Ema approval (brief §9)."""
    if not ema_ok:
        return {'error':'active mode requires explicit Ema approval (production-affecting)'}
    return set_mode('active', by='Ema+Lumi')

if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='set':
        print(set_mode(sys.argv[2]))
    else:
        print(get())
