"""Deterministic geometry tests for hid/compose_v8.py (no ffmpeg needed)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hid'))
import compose_v8 as C

PW8 = os.path.join(os.path.dirname(__file__), '..', 'hid', 'calib', 'pw8.json')

def test_pw8_canvas_locked():
    calib = C.load_calib(PW8)
    seg = [s for s in calib['segments'] if s['name'] == 'TL'][0]
    fc, w, h = C.build_fc(seg, 55.4)
    assert w == 1080 and h == 1442, (w, h)

def test_fc_deterministic():
    calib = C.load_calib(PW8)
    seg = sel = [s for s in calib['segments'] if s['name'] == 'TL'][0]
    a = C.build_fc(seg, 55.4)
    b = C.build_fc(seg, 55.4)
    assert a == b

def test_cam_mirror_in_fc():
    calib = C.load_calib(PW8)
    seg = [s for s in calib['segments'] if s['name'] == 'TL'][0]
    fc, _, _ = C.build_fc(seg, 10.0)
    assert 'hflip,crop=368:233:0:8' in fc

def test_game_dominant_guard():
    import pytest
    calib = C.load_calib(PW8)
    seg = json.loads(json.dumps([s for s in calib['segments'] if s['name'] == 'TL'][0]))
    seg['game']['band_h'] = 100
    try:
        C.build_fc(seg, 10.0)
        assert False, 'guard should have fired'
    except ValueError:
        pass

def test_evenize():
    assert C.evenize(1441) == 1442
    assert C.evenize(1442) == 1442

def test_pick_segment():
    calib = C.load_calib(PW8)
    assert C.pick_segment(calib, 100)['name'] == 'TL'
    assert C.pick_segment(calib, 16000)['name'] == 'BR'
    assert C.pick_segment(calib, 15656.5)['name'] == 'BR'
