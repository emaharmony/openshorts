#!/usr/bin/env python3
"""HID qa_struct.py — Phase 4: structured QA verdicts + gate-failure repair table.

Verdict format (normalized): {gate: code, status: pass|fail|unknown, severity: critical|major|minor,
  value, threshold, method: deterministic|vision, evidence: [paths], explanation}

Deterministic checks (ffmpeg, no model cost):
  PROBE_DURATION   — rendered dur within ±0.3s of expected (content + 0.12 compose pad respected)
  PROBE_STREAMS    — h264 video + aac audio present
  PROBE_RES        — 1080x1964 (v8 canvas) or manifest-declared
  AUDIO_PRESENT    — max_volume > -50dB over sampled bins
  NO_BLACK_TAIL    — YAVG of final 0.4s > 16 (deterministic luma floor)
  NO_BLACK_HEAD    — YAVG of first 0.4s > 16
  FILE_AVAILABLE   — exists && size > 200KB

Vision gates (verdicts filled by Lumi's image reads, scaffolded here):
  CAM_INTEGRITY / SEAM_BLEED / NO_HOOK_OVERLAY / CAPTION_POLICY / TITLE_FIDELITY

REPAIR_TABLE: gate → action + arbiter. Repairs ≤ MAX_ATTEMPTS per clip; versioned outputs
(_r1, _r2) — originals never overwritten (idempotent). Unresolvable → rejected/escalated.
"""
import os
import json, subprocess, os, time

MAX_ATTEMPTS = 2
HID = os.path.dirname(os.path.abspath(__file__))

def ffprobe(path):
    r = subprocess.run(['ffprobe','-v','error','-show_entries',
        'format=duration:stream=codec_type,codec_name,width,height','-of','json',path],
        capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout or '{}')

def luma_avg(path, ss, dur=0.4):
    r = subprocess.run(['ffmpeg','-hide_banner','-nostats','-ss',str(ss),'-t',str(dur),'-i',path,
        '-vf','signalstats,metadata=print:key=lavfi.signalstats.YAVG','-f','null','-'],
        capture_output=True, text=True, timeout=180)
    vals=[float(x.split('=')[1]) for x in (r.stderr or '').splitlines() if 'YAVG=' in x]
    return (sum(vals)/len(vals)) if vals else None

def vol_max(path, bins=5, bin_dur=10.0):
    mx = -99.0
    probe = ffprobe(path)
    d = float((probe.get('format',{}).get('duration')) or 0)
    import re
    for i in range(min(bins, max(1,int(d//bin_dur)))):
        ss = i * min(bin_dur, d/ (bins or 1))
        r = subprocess.run(['ffmpeg','-hide_banner','-nostats','-ss',f'{ss:.1f}','-t',str(min(bin_dur,d-ss)),
            '-i',path,'-map','0:a?','-af','volumedetect','-f','null','-'],
            capture_output=True, text=True, timeout=120)
        m = re.search(r'max_volume: (-?[\d.]+) dB', r.stderr)
        if m: mx = max(mx, float(m.group(1)))
    return mx

def deterministic_checks(path, expected_dur, canvas=(1080,1964)):
    checks=[]
    def add(code, ok, value, thr, expl, evidence=None, status=None):
        checks.append({'gate':code,'status':('pass' if ok else 'fail') if status is None else status,
                       'severity':'critical','value':value,'threshold':thr,
                       'method':'deterministic','explanation':expl,'evidence':evidence or [path]})
    if not os.path.exists(path) or os.path.getsize(path)<200000:
        add('FILE_AVAILABLE', False, 'missing/tiny', '>200KB', 'render file missing or truncated'); return checks
    add('FILE_AVAILABLE', True, os.path.getsize(path)//1024, '>200KB KB', 'file present')
    try: probe=ffprobe(path)
    except Exception as e:
        add('PROBE_STREAMS', False, str(e)[:80], 'h264+aac', 'ffprobe failure'); return checks
    streams=probe.get('streams',[])
    has_v=any(s.get('codec_type')=='video' and s.get('codec_name')=='h264' for s in streams)
    has_a=any(s.get('codec_type')=='audio' and s.get('codec_name')=='aac' for s in streams)
    add('PROBE_STREAMS', has_v and has_a, f"v={has_v} a={has_a}", 'h264+aac', 'stream codecs')
    vd=next((s for s in streams if s.get('codec_type')=='video'), {})
    add('PROBE_RES', (vd.get('width'),vd.get('height'))==(canvas[0],canvas[1]),
        f"{vd.get('width')}x{vd.get('height')}", f"{canvas[0]}x{canvas[1]}", 'render resolution')
    dur=float(probe.get('format',{}).get('duration') or -1)
    add('PROBE_DURATION', abs(dur-expected_dur)<=0.35, round(dur,2), f"{expected_dur:.2f}±0.35s", 'rendered duration vs expected')
    m_a=vol_max(path); add('AUDIO_PRESENT', m_a>-50.0, m_a, '>-50dB', 'audio loudness (volumedetect)')
    # video-stream duration (packet-level truth): protects against audio-only tails (black-tail class)
    r_v=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration',
        '-of','csv=p=0',path],capture_output=True,text=True,timeout=60)
    try: vdur=float(r_v.stdout.strip())
    except Exception: vdur=-1
    add('PROBE_VDURATION', vdur >= expected_dur-0.5 and vdur <= expected_dur+0.5,
        round(vdur,2), f'{expected_dur:.2f}±0.5s', 'video stream duration (packet count truth)')
    d_safe=max(0.0, min(dur, vdur if vdur>0 else dur)-0.45)
    y_end=luma_avg(path, d_safe)
    ok_tail = (y_end is not None and y_end>16)
    add('NO_BLACK_TAIL', ok_tail, y_end, '>16 YAVG', 'luma at video-stream tail (None = no video frames = fail)')
    y_beg=luma_avg(path, 0.0); add('NO_BLACK_HEAD', (y_beg or 0)>16, y_beg, '>16 YAVG', 'first 0.4s luma')
    return checks

def extract_qa_frames(path, dur):
    fr=[]
    for tag,tt in (('first',0.5),('mid',dur/2),('last',dur-1.0)):
        out=f'{HID}/qafixtures/{os.path.basename(path)[:24]}_{tag}.png'
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not os.path.exists(out):
            subprocess.run(['ffmpeg','-y','-loglevel','error','-ss',f'{tt:.2f}','-i',path,
                            '-frames:v','1',out],check=True,timeout=180)
        fr.append(out)
    return fr

REPAIR_TABLE = {
 'NO_BLACK_TAIL':   {'action':'re-render with canvas d dur = content dur (base_dur fix)','critical':True,'automated':True},
 'NO_BLACK_HEAD':   {'action':'shift in-point +0.2s (or +2px frame check), re-render','critical':True,'automated':True},
 'AUDIO_PRESENT':   {'action':'inspect source-window audio; remux/normalize only if source has audio; else reject','critical':True,'automated':'conditional'},
 'PROBE_DURATION':  {'action':'re-render with corrected -t','critical':True,'automated':True},
 'PROBE_RES':       {'action':'re-render with canvas param from template','critical':True,'automated':True},
 'PROBE_STREAMS':   {'action':'re-render; if repeats = template bug, reject+escalate','critical':True,'automated':True},
 'CAM_INTEGRITY':   {'action':'headroom pad (APPROVAL-GATED) or window re-select; if gated-unapproved -> escalate to Ema','critical':True,'automated':False},
 'SEAM_BLEED':      {'action':'SOURCE-COMPARE PROBE FIRST (deterministic arbiter); real bleed within ±2px of spec = spec-alignment fix (auto); beyond = escalate','critical':True,'automated':'probe-first'},
 'NO_HOOK_OVERLAY': {'action':'template bug — reject + escalate (should be unreachable)','critical':True,'automated':False},
 'CAPTION_POLICY':  {'action':'pentakewl never burns; if burned text found = template bug, reject+escalate','critical':True,'automated':False},
}

def plan_repair(failed_gate):
    r=REPAIR_TABLE.get(failed_gate)
    if not r: return {'action':'no mapping — escalate','automated':False}
    return r

def run_repair_loop(render_path, expected_dur, repair_fn, vision_verdicts=None, max_attempts=MAX_ATTEMPTS):
    """render_path: current render; repair_fn(version_id, failed_gates) -> new path or None.
    Returns {history:[...], final_status: approved|rejected|escalated, final_path}"""
    history=[]
    cur=render_path; attempt=0
    deterministic=deterministic_checks(cur,expected_dur)
    failed=[c['gate'] for c in deterministic if c['status']=='fail']
    record={'attempt':0,'render':cur,'failed_gates':failed,'deterministic':deterministic}
    history.append(record)
    vfail=[v['gate'] for v in (vision_verdicts or []) if v['status']=='fail']
    failed=sorted(set(failed+vfail))
    while failed and attempt<max_attempts:
        attempt+=1
        gated=[g for g in failed if not REPAIR_TABLE.get(g,{}).get('automated') in (True,'conditional','probe-first')]
        if gated:
            return {'history':history,'final_status':'escalated','final_path':cur,
                    'escalate_reason':f"gates require Ema/arbiter: {gated}"}
        new=repair_fn(attempt, failed)
        if not new:
            return {'history':history,'final_status':'rejected','final_path':cur,
                    'reject_reason':'repair produced no render'}
        post=deterministic_checks(new,expected_dur)
        still=[c['gate'] for c in post if c['status']=='fail']
        history.append({'attempt':attempt,'render':new,'failed_gates':still,'deterministic':post})
        cur=new
        failed=still
    if failed:
        return {'history':history,'final_status':'rejected','final_path':cur,
                'reject_reason':f"unresolved after {max_attempts} attempts: {failed}"}
    return {'history':history,'final_status':'approved','final_path':cur}

if __name__=='__main__':
    print("qa_struct v0.1 — gate codes:", list(REPAIR_TABLE.keys()))
