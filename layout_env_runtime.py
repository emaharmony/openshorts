"""Apply a job's layout env to THIS process around a render call.

The layout gates (SCREENCAST_LAYOUT, SPLIT_LAYOUT, PUNCH_IN, SPEAKER_*…) are
module-level constants read from the environment exactly once, at import. A
job that asks for layouts=["screencast"] gets them via layout_env() in app.py,
which sets the vars on the spawned ``python main.py`` child. Rerenders
(/api/clip/rerender with framing=auto → reframe=True), however, render inside
the backend process, where those vars are unset: the gates read "0" at import
and an INSET band-stack rerender would silently come back as sliced
TRACK/GENERAL crops (found 15-oct-2026 while re-rendering job a99e1bf5's
wide scenes; the child's log printed ``[layouts] job=… enabled=['SCREENCAST_LAYOUT']``
but the backend env had nothing).

apply(layouts) mutates both os.environ and the already-imported gate modules,
then restores both, so the override lives exactly as long as the call.
"""
import contextlib
import os

# Mirrors app.py's LAYOUT_ENV + LAYOUT_IMPLIES; duplicated here (not imported)
# because importing app.py from a worker thread drags in the whole FastAPI app.
_LAYOUT_ENV = {
    "split": "SPLIT_LAYOUT",
    "screencast": "SCREENCAST_LAYOUT",
    "speaker_cut": "SPEAKER_CUT",
    "punch_in": "PUNCH_IN",
}
_LAYOUT_IMPLIES = {
    "split": ["SPEAKER_SIGNAL"],
    "speaker_cut": ["SPEAKER_SIGNAL"],
}

# The deployment's fixed output policy (main.py hard-sets it for every
# spawned job: FIXED_BAND_LAYOUT=1 + SCREENCAST_LAYOUT=1). A rerender that
# carries no explicit 'layouts' key — older job metadata never recorded it —
# must still render under the policy the job was originally made with, so an
# empty list defaults there instead of toggling nothing (job 85ca7d9d,
# 18-oct-2026: metadata.json has no 'layouts' key, and an empty apply()
# would have re-rendered its clips as plain v2 crops instead of the
# fixed-band stack).
_DEFAULT_POLICY_ENV = {
    "FIXED_BAND_LAYOUT": "1",
    "SCREENCAST_LAYOUT": "1",
}


def _gate_modules():
    """The layout-gate modules this process has imported (best effort)."""
    import sys
    for name in ("screencast_layout", "split_layout", "active_speaker",
                 "punch_in"):
        mod = sys.modules.get(name)
        if mod is not None:
            yield name, mod


def env_for(layouts):
    """The os.environ dict layout_env() in app.py would set for these layouts."""
    env = {}
    for name in layouts or []:
        key = str(name).strip().lower()
        if key == "auto":
            env["AUTO_LAYOUT"] = "1"
            continue
        if key == "none":
            env["AUTO_LAYOUT"] = "0"
            continue
        var = _LAYOUT_ENV.get(key)
        if not var:
            continue
        env[var] = "1"
        for extra in _LAYOUT_IMPLIES.get(key, []):
            env[extra] = "1"
    if not env:
        # No explicit layout → the deployment's default policy (see
        # _DEFAULT_POLICY_ENV for why).
        env.update(_DEFAULT_POLICY_ENV)
    return env


@contextlib.contextmanager
def apply(layouts):
    """Set the layout gates for the enclosed render, then restore them.

    Sets os.environ AND flips the ENABLED/CUT_MODE constants of any gate
    module already imported, because those were frozen at import time.
    """
    env = env_for(layouts)
    if not env:
        yield
        return

    saved_env = {k: os.environ.get(k) for k in env}
    os.environ.update(env)

    saved_flags = []
    try:
        for name, mod in _gate_modules():
            for attr in ("ENABLED", "CUT_MODE"):
                if hasattr(mod, attr):
                    saved_flags.append((mod, attr, getattr(mod, attr)))
                    setattr(mod, attr, True)
        yield
    finally:
        for mod, attr, value in saved_flags:
            setattr(mod, attr, value)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v