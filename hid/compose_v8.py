#!/usr/bin/env python3
"""compose_v8.py — parametric v8 band composer (locked-philosophy layout).

v8 philosophy (Ema-approved, pw8 final): a slim full-width CAM band stacked
on TOP of a DOMINANT gameplay band. No blur fill, no PiP, no chat rendering.
Camera is hflip'd (mirror) per source convention. Canvas even-ized upward to
an even height (libx264 yuv420p requires even dims).

Geometry comes from a per-VOD calibration JSON (MANDATORY per-VOD — the OBS
scene changes between streams and between scenes within one stream):

{
  "name": "f38",
  "segments": [
    {
      "name": "BL",
      "match": {"time_start": 0, "time_end": null},
      "cam":  {"crop": [636, 393, 10, 637], "hflip": true,  "band_h": 684},
      "game": {"crop": [1560, 940, 250, 26], "band_h": 740}
    }
  ],
  "canvas_w": 1080
}

  crop = [w, h, x, y] in SOURCE pixels (1920x1080 for f38; pw8 was 1280x720).
  band_h = target height of that band in the 1080-wide canvas (auto-scaled
  from crop aspect; explicit band_h overrides for the locked look).

Usage:
  python3 compose_v8.py render --calib hid/calib/f38.json \
      --segment BL --src input.mp4 --start 5645.0 --dur 58.0 --out out.mp4
  python3 compose_v8.py fc --calib hid/calib/f38.json --segment BL \
      --dur 58.0   # print filter_complex only (deterministic, testable)
"""
import argparse
import json
import os
import subprocess


def evenize(n):
    return n if n % 2 == 0 else n + 1


def load_calib(path):
    with open(path) as f:
        c = json.load(f)
    assert "segments" in c and c["segments"], "calib json needs segments[]"
    return c


def pick_segment(calib, t):
    """Choose the scene segment whose [start,end) covers t (None = open)."""
    for seg in calib["segments"]:
        m = seg.get("match", {})
        a = m.get("time_start", 0)
        b = m.get("time_end")
        if t >= a and (b is None or t < b):
            return seg
    raise SystemExit(f"no segment covers t={t} in calib")


def band_fc(label, src_box, out_w, band_h, hflip, y, dur):
    w, h, x, y0 = src_box
    chain = f"[{label}v]crop={w}:{h}:{x}:{y0},scale={out_w}:{band_h},setsar=1[{label}]"
    return chain, y


def build_fc(seg, dur, canvas_w=1080, head_pad=0):
    """Deterministic filter_complex for one segment. Head-safety: cam band
    height auto-grows (even-ized) to include the full crop; game band takes
    the remainder (min 30% canvas guard). Geometry LOCKED in the calib file;
    this function only performs arithmetic."""
    cw, ch, cx, cy = seg["cam"]["crop"]
    gw, gh, gx, gy = seg["game"]["crop"]
    cam_h = seg["cam"].get("band_h") or int(round(canvas_w * ch / cw))
    game_h = seg["game"].get("band_h") or int(round(canvas_w * gh / gw))
    cam_h, game_h = evenize(cam_h), evenize(game_h)
    total = evenize(cam_h + game_h)
    if game_h < 0.3 * total:
        raise ValueError(f"game band too small ({game_h}/{total}); v8 requires dominant gameplay")
    src_size = seg.get("src_size")  # optional guard
    hf = "hflip," if seg["cam"].get("hflip", True) else ""
    fc = (
        f"color=black:s={canvas_w}x{total}:d={dur:.3f}:r=30[base];"
        f"[0:v]split=2[g0][c0];"
        f"[c0]{hf}crop={cw}:{ch}:{cx}:{cy},scale={canvas_w}:{cam_h},setsar=1[cam];"
        f"[g0]crop={gw}:{gh}:{gx}:{gy},scale={canvas_w}:{game_h},setsar=1[game];"
        f"[base][cam]overlay=x=0:y=0:shortest=1[v1];"
        f"[v1][game]overlay=x=0:y={cam_h}:shortest=1,setsar=1[v]"
    )
    return fc, canvas_w, total


def render(calib_path, segment, src, out, start, dur, canvas_w=1080, extra=None):
    calib = load_calib(calib_path)
    seg = next((s for s in calib["segments"] if s["name"] == segment), None)
    if seg is None:
        seg = pick_segment(calib, start)
    fc, w, h = build_fc(seg, dur, canvas_w)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    cmd += ["-ss", f"{max(0, start - 0.12):.3f}", "-i", src]
    cmd += ["-t", f"{dur + 0.12:.3f}", "-filter_complex", fc]
    cmd += ["-map", "[v]", "-map", "0:a?"]
    cmd += ["-af", "loudnorm=I=-15.7:TP=-1.5:LRA=11"]  # playbook audio bar (pw8 delivery level)
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19"]
    cmd += ["-c:a", "aac", "-b:a", "160k", out]
    if extra:
        cmd += extra
    subprocess.run(cmd, check=True)
    return {"out": out, "fc": fc, "canvas": f"{w}x{h}"}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("fc")
    p1.add_argument("--calib", required=True)
    p1.add_argument("--segment", required=True)
    p1.add_argument("--dur", type=float, default=60.0)
    p1.add_argument("--t", type=float, help="source time to auto-pick segment")
    p1.add_argument("--canvas-w", type=int, default=1080)
    p2 = sub.add_parser("render")
    p2.add_argument("--calib", required=True)
    p2.add_argument("--segment", required=True)
    p2.add_argument("--src", required=True)
    p2.add_argument("--out", required=True)
    p2.add_argument("--start", type=float, required=True)
    p2.add_argument("--dur", type=float, required=True)
    args = ap.parse_args()
    calib = load_calib(args.calib)
    seg = next((s for s in calib["segments"] if s["name"] == args.segment), None)
    if getattr(args, 't', None) is not None:
        seg = pick_segment(calib, args.t)
    if args.cmd == "fc":
        fc, w, h = build_fc(seg, args.dur, args.canvas_w)
        print(fc)
        print(f"canvas: {w}x{h}", file=__import__('sys').stderr)
    else:
        import sys
        r = render(args.calib, args.segment, args.src, args.out, args.start, args.dur)
        print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
