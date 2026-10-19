"""Find the webcam inset in a screen recording, and frame the two apart.

The case: one source, the whole screen (a game, a desktop, an editor) with the
person composited into a corner. It is how OBS records and how every stream VOD
looks, and it is the case screencast_layout gets wrong. There the speaker band
is a large crop taken AROUND the face, which on a full-screen source means the
band is mostly more screen: measured on an Excel walkthrough, the output showed
the same spreadsheet twice, once whole and once enlarged.

What this needs instead is the inset's own rectangle, so the two bands can hold
genuinely different things — screen above, person below.

Finding it exactly is harder than it looks. The inset is not always a rectangle
(circles and clipped polygons are common), it has no reliable border, and on
gameplay the background moves as much as the person does, which rules out
temporal-variance tricks. What IS reliable is that the inset is anchored to a
corner and that a person detector fires inside it. So: locate the person, decide
which corner they are nearest, and grow a box from that corner until it covers
them with margin.
"""
import os

from ffmpeg_utils import blurred_backdrop

CORNER_MARGIN = 0.20   # a subject this far from an edge (as a fraction of the
                       # frame) still counts as anchored to it

# An inset subject is SMALL and OFF-CENTRE; a presenter filling the shot is
# neither. Requiring the detection to actually touch two edges was tried first
# and rejected: YOLO returns an upper-body box that stops at the chest, so a
# webcam pinned to the right edge measured 18% clear of the bottom and got
# thrown out. Measured on four real clips, these two properties separate the
# cases where "touching a corner" did not.
MAX_SUBJECT_HEIGHT = 0.35   # fraction of frame height

# Horizontal offset from centre, as a fraction of frame width. HORIZONTAL
# specifically: a composited camera is pinned to the left or right side, while a
# talking head is centred left-to-right even when their face sits high in the
# shot. Accepting offset on either axis let four talking heads through, all of
# them with a face near the top edge. Measured on those nine candidates the two
# groups do not overlap: real insets sat 0.37-0.43 from centre, the talking
# heads 0.01-0.12.
MIN_OFFSET = 0.18

# How much bigger than the detected head/upper body the inset is assumed to be.
# A webcam frames head and shoulders, and detectors return the head or the upper
# body, so the box has to grow to reach the inset's real edges.
INSET_PADDING = float(os.environ.get("INSET_PADDING", "1.45"))

# Guard rails as a fraction of frame height. Below the floor there is nothing
# worth showing; above the ceiling it stopped being an inset and the layout
# should not be used at all.
MIN_INSET_HEIGHT = 0.10
MAX_INSET_HEIGHT = 0.38

# An inset is pinned to the same pixels for the whole recording; a presenter
# walks about. Spread of the detected centres, as a fraction of frame width,
# above which this is a person in a room rather than a composited camera.
# Measured on the two false positives this rule was written for: a real inset
# moved 3-11px across samples, a presenter 316px.
MAX_CENTRE_SPREAD = 0.05

# Room kept above the detection, as a fraction of its height (see inset_box).
FACE_HEADROOM = 0.35
BODY_HEADROOM = 0.10

# A webcam window frames head and shoulders: the face is about a third of its
# width. Used for overlays that float mid-screen, where inset_box's corner
# anchoring does not apply and pushed the crop up onto the ceiling, and to grow
# a face detection to the inset in a corner.
OVERLAY_FACE_WIDTHS = 3.0


def nearest_corner(box, frame_w, frame_h):
    """Which corner the subject sits in: (horizontal, vertical) as strings.

    Returns e.g. ("left", "bottom"). A subject in the middle of the frame is
    reported by its nearest edges anyway; callers use `is_cornered` to reject.
    """
    cx = box[0] + box[2] / 2.0
    cy = box[1] + box[3] / 2.0
    return ("left" if cx < frame_w / 2 else "right",
            "top" if cy < frame_h / 2 else "bottom")


def is_cornered(box, frame_w, frame_h, margin=CORNER_MARGIN):
    """True when the subject looks like a webcam inset rather than the shot.

    Small and off-centre, not "touches two edges": see MAX_SUBJECT_HEIGHT.

    This is a sanity filter, not the decision. Whether the video is a screen
    recording with a camera in it at all is answered upstream by layout_picker;
    a game character standing in a corner would pass this test, and is kept out
    by the fact that nobody asked for this layout on that video.
    """
    x, y, w, h = box
    if h > frame_h * MAX_SUBJECT_HEIGHT:
        return False

    cx = (x + w / 2.0) / frame_w
    off_centre = abs(cx - 0.5) >= MIN_OFFSET

    near_edge = (x <= frame_w * margin or (x + w) >= frame_w * (1 - margin)
                 or y <= frame_h * margin or (y + h) >= frame_h * (1 - margin))
    return off_centre and near_edge


INSET_ASPECT = 16 / 9.0


def _place(x, y, w, h, new_w, new_h, frame_w, frame_h, horizontal, vertical):
    """Top-left corner of a new_w x new_h box grown around the detection."""
    # Anchor: keep the edge the subject is already near, grow the other way.
    if horizontal == "left":
        new_x = max(0, min(x - (new_w - w) / 2.0, frame_w - new_w))
        if x <= frame_w * CORNER_MARGIN:
            new_x = 0
    else:
        new_x = max(0, min(x + w + (new_w - w) / 2.0 - new_w, frame_w - new_w))
        if (x + w) >= frame_w * (1 - CORNER_MARGIN):
            new_x = frame_w - new_w

    # Vertical growth is biased upwards: detectors return the head or the chest,
    # and a portrait needs headroom, not more torso. Splitting the growth evenly
    # cropped the top of the head off on real clips.
    grow = new_h - h
    if vertical == "top":
        new_y = max(0, min(y - grow * 0.6, frame_h - new_h))
        if y <= frame_h * CORNER_MARGIN:
            new_y = 0
    else:
        # Pin to the bottom edge: the inset is there, and the detection sits
        # somewhere inside it rather than at its top.
        new_y = frame_h - new_h
        if (y + h) < frame_h * (1 - CORNER_MARGIN):
            new_y = max(0, min(y - grow * 0.6, frame_h - new_h))
    return new_x, new_y


def inset_box(box, frame_w, frame_h, padding=None, face=False):
    """Estimated inset rectangle (x, y, w, h) around a detected subject.

    Grown from the corner the subject is anchored to, so the box hugs the same
    edges the inset does instead of floating around the face.

    The height comes from assuming a 16:9 inset rather than from scaling the
    detection, because the detection is often a torso: YOLO returned a 246x86
    box for a webcam whose real rectangle was about 325x180, and padding that
    shape upwards still cut the head off. Deriving the height from the width
    and pinning the result to the corner reaches the top of the inset instead.

    ``face`` says the detection is a face box, not YOLO's upper body. A face is
    a third of a webcam's width (OVERLAY_FACE_WIDTHS), not 1/1.45 of it: grown
    by the body padding, a 128px face on a 720p Excel walkthrough gave a
    181px box pinned to the bottom edge that started 41px below the top of
    the face, and the enlarged band showed a forehead-less face (17-oct-2026).
    """
    if padding is None:
        padding = OVERLAY_FACE_WIDTHS if face else INSET_PADDING
    x, y, w, h = box
    horizontal, vertical = nearest_corner(box, frame_w, frame_h)

    new_w = min(frame_w, w * padding)
    # A face box is square, so tripling its height too would make a portrait
    # crop; the 16:9 assumption alone sets the height.
    new_h = new_w / INSET_ASPECT if face else max(h * padding, new_w / INSET_ASPECT)
    new_h = min(frame_h, new_h)
    # Never start below the head. A face box stops at the brows, so the hair
    # needs about a third of its height on top; YOLO's box already starts at
    # the top of the head.
    top_limit = max(0.0, y - h * (FACE_HEADROOM if face else BODY_HEADROOM))

    new_x, new_y = _place(x, y, w, h, new_w, new_h, frame_w, frame_h,
                          horizontal, vertical)
    if new_y > top_limit:
        if new_y + new_h >= frame_h - 1:
            # Pinned to the bottom edge: grow upwards (and keep 16:9) rather
            # than slide off the edge the inset sits on.
            new_h = frame_h - top_limit
            new_w = min(frame_w, max(new_w, new_h * INSET_ASPECT))
            new_x, _ = _place(x, y, w, h, new_w, new_h, frame_w, frame_h,
                              horizontal, vertical)
        new_y = top_limit

    return (int(round(new_x)), int(round(new_y)),
            int(round(new_w)), int(round(new_h)))


def usable(box, frame_h, min_ratio=MIN_INSET_HEIGHT, max_ratio=MAX_INSET_HEIGHT):
    """Whether an inset of this size is worth building a layout around."""
    return min_ratio * frame_h <= box[3] <= max_ratio * frame_h


def detect(video_path, samples=10, fallback_box=None):
    """Median inset rectangle across sampled frames, or None.

    None means "no usable inset here", which callers must treat as "use
    another layout" rather than as an error.

    ``fallback_box``: a box recorded for this source earlier (an OBS composite
    column is constant for a whole stream, so a job that already detected it
    on the full source keeps it across per-clip renders). Adopted only when
    the detectors confirm the webcam is still there — on the very clip whose
    dim lighting made ``detect`` fail (job 85ca7d9d clip_1) the crop-zoom
    rescue in ``present_in_scene`` still finds the person, so the check is
    real evidence, not a rubber stamp.
    """
    import cv2
    import numpy as np
    import main as m
    import screencast_layout

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if total <= 0 or not frame_w:
        cap.release()
        return None

    boxes = []
    try:
        for i in range(samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / samples))
            ok, frame = cap.read()
            if not ok:
                continue
            # Faces first, body as fallback: a webcam inset is small, and on a
            # 1080p source the face inside it is often too few pixels for
            # BlazeFace even at full resolution, while YOLO still finds the
            # person.
            faces = screencast_layout.detect_faces_full_res(frame)
            if faces:
                box = max(faces, key=lambda c: c['score'])['box']
            else:
                box = m.detect_person_yolo(frame)
            if not box:
                continue
            if not is_cornered(box, frame_w, frame_h):
                continue
            boxes.append(inset_box(box, frame_w, frame_h, face=bool(faces)))
    finally:
        cap.release()

    if len(boxes) < max(3, samples // 3):
        return _confirm_fallback(video_path, frame_w, frame_h, fallback_box)

    found = stable_box(boxes, frame_w, frame_h)
    if found:
        return found
    return _confirm_fallback(video_path, frame_w, frame_h, fallback_box)


def _confirm_fallback(video_path, frame_w, frame_h, fallback_box):
    """Validate a recorded box for this source when fresh detection fails.

    The OBS composite column is baked into the stream recording, so the box
    detected on the full source stays correct for any clip cut from it — but
    only while the camera really sits in it in THIS clip. ``present_in_scene``
    supplies that proof with a single source of truth (the same detectors the
    fresh path uses); a clip the camera left never adopts the fallback.
    """
    if not fallback_box or len(fallback_box) != 4:
        return None
    box = tuple(int(round(v)) for v in fallback_box)
    x, y, w, h = box
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return None
    if x + w > frame_w or y + h > frame_h:
        return None
    if not is_composite_column(box, frame_w, frame_h):
        # Fallbacks only ever carry composite columns (job metadata's
        # ``inset_box``); a stored bubble box must not bypass fresh detection
        # because bubbles move and the recorder may reposition them.
        return None
    import cv2
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else 0
    cap.release()
    if total <= 0 or not present_in_scene(video_path, box, 0, max(total - 1, 1)):
        return None
    print(f"   📹 Webcam inset (from job record): {box}")
    return box


def stable_box(boxes, frame_w, frame_h, min_agree=3):
    """Median of the inset boxes that agree with each other, or None."""
    import numpy as np

    arr = np.array(boxes, dtype=float)

    # Stability gate. Without it, a presenter standing in front of a screen and
    # an ordinary talking head both come back as "insets" and the layout puts a
    # zoom of someone's face under a copy of the same shot.
    #
    # Measured against the plain min-to-max range first, which was far too
    # brittle: one sample landing on a face elsewhere in the frame killed three
    # genuine insets. So cluster around the median instead and require most
    # detections to agree, which tolerates the odd stray without tolerating a
    # subject that actually moves.
    centres_x = arr[:, 0] + arr[:, 2] / 2.0
    centres_y = arr[:, 1] + arr[:, 3] / 2.0
    mid_x, mid_y = np.median(centres_x), np.median(centres_y)
    tolerance = frame_w * MAX_CENTRE_SPREAD
    close = ((np.abs(centres_x - mid_x) <= tolerance)
             & (np.abs(centres_y - mid_y) <= tolerance))
    if close.sum() < max(min_agree, 0.6 * len(boxes)):
        return None

    arr = arr[close]
    median = tuple(int(v) for v in np.median(arr, axis=0))
    if not usable(median, frame_h):
        return None
    return median


def overlay_box(box, frame_w, frame_h, widen=OVERLAY_FACE_WIDTHS):
    """A 16:9 box centred on a detected face (or upper body), clamped."""
    x, y, w, h = box
    new_w = min(frame_w, w * widen)
    new_h = min(frame_h, new_w / INSET_ASPECT)
    cx, cy = x + w / 2.0, y + h / 2.0
    new_x = max(0, min(cx - new_w / 2.0, frame_w - new_w))
    new_y = max(0, min(cy - new_h * 0.45, frame_h - new_h))
    return (int(round(new_x)), int(round(new_y)),
            int(round(new_w)), int(round(new_h)))


def detect_in_scene(video_path, start_f, end_f, samples=5):
    """A presenter window laid over the screen in this one scene, or None.

    ``detect`` is the clip-wide check and insists on a corner, because nothing
    upstream of it says the frame is a screen. Here the shot check already did
    (this runs only on scenes Gemini called "screen"), so a small face that
    stays put is the presenter's camera wherever it floats: a QuickTime or Loom
    window over a document sits mid-left, not in a corner, and the screen-only
    layout shrank both into a 1080px-wide strip (Ty Myers tutorial,
    6-oct-2026). What still rules a subject out: being big (that is the shot,
    not an overlay) or moving between samples.

    The caller only asks where the shot check said a live presenter camera is
    laid over the screen (presenter_cam). That gate is what keeps game
    characters, photos on slides and cover art out; the YOLO body fallback
    stays because BlazeFace misses the webcam face in about half the samples
    of a dim or small window (ticker_VUqnFqEHy2E), and without it a real
    presenter window is lost.
    """
    import cv2
    import numpy as np
    import main as m
    import screencast_layout

    if end_f - 1 < start_f:
        return None
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    boxes = []
    try:
        for f_idx in np.linspace(start_f, end_f - 1, samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(f_idx)))
            ok, frame = cap.read()
            if not ok:
                continue
            faces = screencast_layout.detect_faces_full_res(frame)
            if faces:
                box = max(faces, key=lambda c: c['score'])['box']
                widen = OVERLAY_FACE_WIDTHS
            else:
                box = m.detect_person_yolo(frame)
                widen = INSET_PADDING
            if not box or box[3] > frame_h * MAX_SUBJECT_HEIGHT:
                continue
            boxes.append(overlay_box(box, frame_w, frame_h, widen))
    finally:
        cap.release()
    need = samples // 2 + 1
    if len(boxes) < need:
        return None
    return stable_box(boxes, frame_w, frame_h, min_agree=need)


def _centre_inside(det, box, slack):
    cx = det[0] + det[2] / 2.0
    cy = det[1] + det[3] / 2.0
    x, y, w, h = box
    return (x - slack <= cx <= x + w + slack) and (y - slack <= cy <= y + h + slack)


def present_in_scene(video_path, box, start_f, end_f, samples=3):
    """Whether the webcam really sits in ``box`` during this scene.

    ``detect`` finds the box once per clip, from samples spread over every
    scene, and a clip cut from a tutorial mixes shots: the bubble is in the
    corner during the screen recording and gone in the editor shot next to it.
    Before this check every screen scene of a clip with an inset anywhere got
    the INSET layout, and on a scene without the camera the bottom band was an
    enlarged crop of a toolbar (measured on a Canva + QuickTime tutorial,
    6-oct-2026). A face or a person whose centre falls in the box in most
    samples is the answer.
    """
    import cv2
    import numpy as np
    import main as m
    import screencast_layout

    if end_f - 1 < start_f:
        return False
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    slack = max(box[2], box[3]) * 0.1
    hits = 0
    try:
        for f_idx in np.linspace(start_f, end_f - 1, samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(f_idx)))
            ok, frame = cap.read()
            if not ok:
                continue
            dets = [c['box'] for c in screencast_layout.detect_faces_full_res(frame)]
            if not any(_centre_inside(d, box, slack) for d in dets):
                person = m.detect_person_yolo(frame)
                dets = [person] if person else []
            if any(_centre_inside(d, box, slack) for d in dets):
                hits += 1
            else:
                # Crop-zoom rescue: the cam face is plainly visible to a human
                # yet both detectors miss it — measured on job a99e1bf5 (the
                # 15-oct-2026 Windwaker QA batch): every sampled frame of
                # clip_8 (VOD 3004-3062s) and clip_7's back half (2573-2599s)
                # shows her face in the bubble, and present_in_scene still
                # returned 0/3 hits, so those scenes rendered WIDE and the
                # batch missed the template. Two stacked causes: BlazeFace
                # misses the ~60px, low-light, angled cam face even at full
                # resolution, and detect_person_yolo scales the whole 1920px
                # frame to DETECT_MAX_WIDTH=640 first, so the ~280px bubble
                # is ~9px of person at inference scale — nothing to find. The
                # same ladder the codebase already climbed for faces (640 ->
                # full-res, see detect_faces_full_res) applied one rung
                # further: crop the frame to the inset box and upscale it
                # ~3x BEFORE detection, then map any hit back to full-frame
                # coords. A scene whose camera truly left shows the video's
                # background there, and a zoomed background grows no face.
                x, y, w, h = [int(round(v)) for v in box]
                fh, fw = frame.shape[:2]
                x = max(0, x); y = max(0, y)
                w = max(8, min(w, fw - x)); h = max(8, min(h, fh - y))
                crop = frame[y:y + h, x:x + w]
                if crop.size:
                    scale = 3.0
                    big = cv2.resize(crop, (int(w * scale), int(h * scale)),
                                     interpolation=cv2.INTER_CUBIC)
                    zoom_dets = [c['box'] for c in
                                 screencast_layout.detect_faces_full_res(big)]
                    if not zoom_dets:
                        person = m.detect_person_yolo(big)
                        zoom_dets = [person] if person else []
                    for d in zoom_dets:
                        # Map the zoomed-crop detection back to full-frame
                        # coordinates before the centre test; detect() found
                        # the box in these same coordinates.
                        d[0] = x + d[0] / scale
                        d[1] = y + d[1] / scale
                        d[2] = d[2] / scale
                        d[3] = d[3] / scale
                        if _centre_inside(d, box, slack):
                            hits += 1
                            break
    finally:
        cap.release()
    return hits * 2 > samples


MAX_CAMERA_RATIO = 0.40

# An OBS-composite source is a stream recording where the layout is baked in:
# a large left column holds the webcam (and often the chat under it) flush
# against the left edge, and the game capture sits beside it as a *window*,
# not fullscreen (job 85ca7d9d, 18-oct-2026: 1280x720, box (0,199,376,211) =
# flush-left, 29.4% of the width). Scaling that frame whole into the screen
# band shrinks the game to a stamp AND bakes chat text into every Short.
# A bubble-cam source (the template batch, 95708adc) also touches a corner,
# but its cam is <20% of the width and the game fills the whole frame —
# whole-frame scaling stays correct there. The width test is what separates
# the two: 0.20 is far above the template batch's bubbles (measured 0.13-0.16)
# and far below this composite (0.294).
COMPOSITE_MIN_WIDTH = 0.20
COMPOSITE_FLUSH_X = 0.02   # box.x this close to the left edge = flush
# Game-crop margin past the column. 0.01 was measured against a single t=2614
# frame, but the detected column edge wobbles ±40px per scene (dim chat rows
# shrink the box), so 356 < 388 (the stable chat-column edge) on small boxes —
# Twitch chat reappeared at the band edge (job 85ca7d9d clips 9/10, 19-oct).
# 0.045 keeps game_x ≥ 396 for boxes down to w=351: past the 388 edge at every
# wobble sampled, and only ~2.9% more source width given up.
COMPOSITE_MARGIN_W = 0.045
COMPOSITE_CAM_RATIO = 0.18  # cam band share of the frame (template ≈ 340/1920)


def is_composite_column(box, orig_w, orig_h):
    """True when ``box`` is the left column of an OBS composite layout."""
    x, y, w, h = box
    return (x <= COMPOSITE_FLUSH_X * orig_w
            and w >= COMPOSITE_MIN_WIDTH * orig_w
            # A column is taller than the 16:9 cam it encloses: the chat
            # underneath extends it (measured 0.293 height on 0.294 width.
            # A pure corner bubble of this width would be ~16:9, 0.165 tall).
            and h >= 0.22 * orig_h)


def inset_filtergraph(orig_w, orig_h, out_w, out_h, box, camera_ratio=None):
    """Screen on top at full width, the webcam inset below.

    The screen keeps its whole width, which is the point: a game HUD or a
    desktop puts what matters at the edges. The inset is scaled up so the person
    reads at a size the source never gave them.

    OBS-composite sources (see is_composite_column) get a different screen
    band: the GAME REGION right of the baked-in cam/chat column is cropped
    and scaled to fill the band, instead of scaling the whole frame (job
    85ca7d9d — whole-frame scaling stamped the game and baked chat text into
    every clip; game-region crop x ≥ 388/1280 measured clean and full-bleed
    at t=2614, with only 10-15px of chat text at the edge at t=702, covered
    by the +1%W margin). The screen keeps its whole width in both modes.
    """
    box_w = max(2, box[2])
    box_h = max(2, box[3])

    composite = is_composite_column(box, orig_w, orig_h)

    if camera_ratio is not None:
        cam_h = int(out_h * camera_ratio)
    elif composite:
        # The composite column carries the cam window whole: honour its box
        # aspect (≈0.32 of a 1080p frame on job 85ca7d9d) instead of the
        # template's 0.18 stamp — that ratio was measured on FULLSCREEN
        # sources with a 0.13-0.16 cam bubble. Stamping 0.18 and centre-
        # cropping the overflow amputated forehead + chin on close-up cams
        # (Ema: "half my face is gone", 19-oct). MAX_CAMERA_RATIO still caps.
        cam_h = int(round(out_w * box_h / float(box_w)))
    else:
        cam_h = int(round(out_w * box_h / float(box_w)))
    cam_h = min(cam_h, int(out_h * MAX_CAMERA_RATIO))
    cam_h -= cam_h % 2

    if composite:
        # Game region: everything right of the baked-in cam/chat column plus
        # 1% of the width of margin (the measured chat bleed). Uniform scale
        # into the band: game 891x720 -> 1080 wide -> 876-tall band.
        game_x = box[0] + box[2] + int(round(COMPOSITE_MARGIN_W * orig_w))
        game_w = orig_w - game_x
        screen_h = int(round(out_w * orig_h / float(game_w)))
        screen_h -= screen_h % 2
        screen_h = max(2, min(screen_h, out_h - cam_h - 2))
        screen_crop = (f"crop=w={game_w}:h={orig_h}:x={game_x}:y=0,"
                       f"scale={out_w}:{screen_h}")
    else:
        screen_h = int(round(out_w * orig_h / float(orig_w)))
        screen_h -= screen_h % 2
        screen_h = max(2, min(screen_h, out_h - cam_h - 2))
        screen_crop = f"scale={out_w}:{screen_h}"

    # Widen (or heighten) the crop to the band's aspect so the scale below is
    # uniform. Clamped to the frame, so an inset hard against an edge simply
    # keeps whatever it can reach. In composite mode the box-aspect band now
    # matches the box exactly, and widening to the target aspect (3:1 old
    # band) would sweep gameplay into the cam crop — keep the box as found.
    target_aspect = out_w / float(cam_h)
    x, y, w, h = box
    if composite:
        pass  # box aspect == band aspect now; nothing to widen
    elif w / float(h) < target_aspect:
        want_w = min(orig_w, int(round(h * target_aspect)))
        x = int(round(x + w / 2.0 - want_w / 2.0))
        w = want_w
    else:
        want_h = min(orig_h, int(round(w / target_aspect)))
        y = int(round(y + h / 2.0 - want_h / 2.0))
        h = want_h
    x = max(0, min(x, orig_w - w))
    y = max(0, min(y, orig_h - h))

    w -= w % 2
    h -= h % 2
    x -= x % 2
    y -= y % 2

    filler_h = out_h - screen_h - cam_h

    if composite:
        # The band now matches the box aspect (no overflow to trim), so this
        # is the plain scale. The old centre-crop version (scale -2 then
        # crop={out_w}:{cam_h}) kept only the middle ~57% of a close-up cam —
        # forehead + chin amputated (job 85ca7d9d, Ema 19-oct).
        cam_chain = (
            f"[ca]crop=w={w}:h={h}:x={x}:y={y},scale={out_w}:{cam_h}[cam]")
    else:
        cam_chain = (
            f"[ca]crop=w={w}:h={h}:x={x}:y={y},scale={out_w}:{cam_h}[cam]")

    return (
        f"[0:v]split=3[bga][sa][ca];"
        # Blurred backdrop so the leftover strip is not a black bar. Scaled by
        # HEIGHT: scaling a 16:9 source to 1080 wide gives 608 tall, and there
        # is no 1920-tall crop to take out of that.
        f"[bga]{blurred_backdrop(out_w, out_h, 14)}[bg];"
        f"[sa]{screen_crop}[screen];"
        f"{cam_chain};"
        f"[bg][screen]overlay=x=0:y={filler_h // 2}[withscreen];"
        f"[withscreen][cam]overlay=x=0:y={filler_h // 2 + screen_h},"
        f"setsar=1[v]"
    )
