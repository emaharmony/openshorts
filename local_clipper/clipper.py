"""Single-worker, local OpenShorts intake. Run with Python 3.10+ on Windows."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"
MEDIA = {".mp4", ".mkv"}
LOCAL_INBOX = Path(os.environ.get("OPENSHORTS_HOST_INBOX", r"D:\clips\openshorts-local-inbox"))
LOCAL_TOKEN = Path(os.environ.get("OPENSHORTS_HOST_TOKEN_FILE", str(Path.home() / ".codex" / "openshorts-local-intake.token")))


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hydrated(path):
    """Check metadata before opening a possible cloud placeholder."""
    st = path.lstat()
    if path.is_symlink() or getattr(st, "st_file_attributes", 0) & (0x400 | 0x1000 | 0x40000 | 0x400000):
        return False
    return path.is_file() and st.st_size > 0


def ready(path):
    """Reject links and files still held open for writing on Windows."""
    if not hydrated(path):
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            return False
        kernel.CloseHandle(handle)
    return True


def move_no_replace(src, dst):
    # Hard-link then unlink supplies atomic no-overwrite creation on both
    # Windows and POSIX, and refuses cross-volume moves.
    os.link(src, dst)
    os.unlink(src)


def request(method, path, data=None, timeout=60, local_auth=False):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if local_auth:
        headers["X-OpenShorts-Local-Token"] = LOCAL_TOKEN.read_text(encoding="ascii").strip()
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


class Worker:
    def __init__(self, root, stable=30, clip_range=None, local_intake=False, original=None):
        self.root = Path(root).resolve(strict=True)
        self.stable = stable
        self.clip_range = clip_range
        self.local_intake = local_intake
        self.original = Path(original).absolute() if original else None
        self.rechecked = set()
        self.seen = {}
        self.internal = self.root / ".local-clipper"
        self.internal.mkdir(exist_ok=True)
        for name in ("working", "failed", "clips", "processed"):
            (self.root / name).mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.internal / "state.sqlite3")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, original TEXT, current TEXT, planned TEXT, fingerprint TEXT, state TEXT, job_id TEXT, clips TEXT, error TEXT, retries INTEGER DEFAULT 0, updated REAL, clip_range TEXT)")
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(jobs)")}
        if "handoff" not in columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN handoff TEXT")
        if "original_mode" not in columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN original_mode INTEGER DEFAULT 0")
        self.db.commit()

    def update(self, ident, **values):
        values["updated"] = time.time()
        self.db.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in values) + " WHERE id=?", (*values.values(), ident))
        self.db.commit()

    def rows(self):
        self.db.row_factory = sqlite3.Row
        return self.db.execute("SELECT * FROM jobs ORDER BY updated").fetchall()

    def retry(self, ident):
        rows = [r for r in self.rows() if r["id"] == ident]
        if not rows or rows[0]["state"] not in ("failed", "interrupted_upload"):
            raise ValueError("Retry requires a failed or interrupted-upload job ID; ambiguous submissions require manual reconciliation")
        values = {"state": "claimed", "error": None, "retries": rows[0]["retries"] + 1}
        if rows[0]["handoff"]:
            values["handoff"] = secrets.token_hex(32) + Path(rows[0]["current"]).suffix.lower()
        self.update(ident, **values)

    def scan(self, filename=None):
        try:
            config = request("GET", "/api/config")
            if config.get("fixedBandPolicy") is not True:
                raise RuntimeError("fixed-band policy unavailable")
            if not self.clip_range and config.get("fixedBandAuto") is not True:
                raise RuntimeError("automatic selector unavailable")
            if self.local_intake and (not config.get("localIntake") or not LOCAL_INBOX.is_dir() or not LOCAL_TOKEN.is_file()):
                raise RuntimeError("local intake unavailable")
        except Exception as exc:
            print(f"Intake blocked: {exc}", file=sys.stderr)
            return None
        for path in ([self.original] if self.original else sorted(self.root.iterdir())):
            if filename is not None and path.name != filename:
                continue
            if path.suffix.lower() not in MEDIA or path.is_symlink():
                continue
            try:
                st = path.lstat()
                if getattr(st, "st_file_attributes", 0) & (0x400 | 0x1000 | 0x40000 | 0x400000):
                    continue
                if not path.is_file():
                    continue
                signature = (st.st_size, st.st_mtime_ns)
                old = self.seen.get(str(path))
                if not old or old[0] != signature:
                    self.seen[str(path)] = (signature, time.monotonic())
                    continue
                if time.monotonic() - old[1] < self.stable or not ready(path):
                    continue
                fingerprint = digest(path)
                if (path.stat().st_size, path.stat().st_mtime_ns) != signature:
                    self.seen.pop(str(path), None)
                    continue
                if self.db.execute("SELECT 1 FROM jobs WHERE fingerprint=?", (fingerprint,)).fetchone():
                    continue
                ident = uuid.uuid4().hex
                if self.original:
                    handoff = secrets.token_hex(32) + path.suffix.lower()
                    self.db.execute("INSERT INTO jobs (id,original,current,fingerprint,state,updated,handoff,original_mode) VALUES (?,?,?,?,'claimed',?,?,1)", (ident, str(path), str(path), fingerprint, time.time(), handoff))
                    self.db.commit()
                    return ident
                job_dir = self.root / "working" / ident
                job_dir.mkdir()
                target = job_dir / path.name
                handoff = secrets.token_hex(32) + path.suffix.lower() if self.local_intake and not self.clip_range else None
                self.db.execute("INSERT INTO jobs (id,original,current,planned,fingerprint,state,updated,clip_range,handoff) VALUES (?,?,?,?,?,'claiming',?,?,?)", (ident, str(path), str(path), str(target), fingerprint, time.time(), json.dumps(self.clip_range) if self.clip_range else None, handoff))
                self.db.commit()
                move_no_replace(path, target)
                self.update(ident, current=str(target), planned=None, state="claimed")
                if digest(target) != fingerprint:
                    self.fail(next(r for r in self.rows() if r['id'] == ident), "source changed during claim")
                return ident
            except (OSError, sqlite3.Error) as exc:
                print(f"Intake deferred: {exc}", file=sys.stderr)
        return None

    def reconcile_moves(self, row):
        if row["state"] not in ("claiming", "archiving", "failing"):
            return
        src, dst = Path(row["current"]), Path(row["planned"])
        if src.exists() and dst.exists():
            if os.path.samefile(src, dst):
                src.unlink()
            else:
                raise RuntimeError("move collision requires manual review")
        elif src.exists():
            move_no_replace(src, dst)
        elif not dst.exists():
            raise RuntimeError("move source and destination missing")
        state = {"claiming": "claimed", "archiving": "completed", "failing": "failed"}[row["state"]]
        self.update(row["id"], current=str(dst), planned=None, state=state)
        if state == "claimed" and digest(dst) != row["fingerprint"]:
            self.fail(next(r for r in self.rows() if r["id"] == row["id"]), "source changed during claim")

    def fail(self, row, message):
        ident = row["id"]
        if row["original_mode"]:
            self.update(ident, state="failed", error=message[:2000])
            return
        src = Path(row["current"])
        fail_dir = self.root / "failed" / ident
        fail_dir.mkdir(exist_ok=True)
        dest = fail_dir / Path(row["original"]).name
        self.update(ident, state="failing", planned=str(dest), error=message[:2000])
        self.reconcile_moves(next(r for r in self.rows() if r["id"] == ident))

    def upload(self, path, upload_url):
        # http.client streams the source; urllib's Request would buffer it.
        import http.client
        from urllib.parse import urlsplit
        url = urlsplit(upload_url)
        if url.hostname not in ("localhost", "127.0.0.1") or url.scheme != "http":
            raise ValueError("upload URL is not local")
        conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=300)
        try:
            conn.putrequest("PUT", url.path)
            conn.putheader("Content-Length", str(path.stat().st_size))
            conn.endheaders()
            with open(path, "rb") as source:
                while block := source.read(1024 * 1024):
                    conn.send(block)
            response = conn.getresponse()
            result = response.read()
            if response.status >= 400:
                raise RuntimeError(f"upload HTTP {response.status}: {result[:500]!r}")
            return json.loads(result)
        finally:
            conn.close()

    def prepare_range(self, path):
        import http.client
        boundary = "localclipper" + uuid.uuid4().hex
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="source{path.suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=300)
        try:
            conn.putrequest("POST", "/api/thumbnail/upload")
            conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length", str(len(head) + path.stat().st_size + len(tail)))
            conn.endheaders()
            conn.send(head)
            with path.open("rb") as source:
                while block := source.read(1024 * 1024):
                    conn.send(block)
            conn.send(tail)
            response = conn.getresponse()
            body = response.read()
            if response.status >= 400:
                raise RuntimeError(f"prepare HTTP {response.status}: {body[:500]!r}")
            return json.loads(body)["session_id"]
        finally:
            conn.close()

    def step(self, row):
        ident, state = row["id"], row["state"]
        if row["handoff"] and (state == "exporting" or (state == "running" and ident not in self.rechecked)):
            source = Path(row["current"])
            stage = LOCAL_INBOX / row["handoff"]
            try:
                verified = hydrated(source) and (row["original_mode"] or os.path.samefile(source, stage)) and digest(source) == row["fingerprint"]
            except OSError:
                verified = False
            if not verified:
                self.update(ident, state="integrity_failed", error="Local source changed; preserving input for manual review")
                return
            self.rechecked.add(ident)
        if state in ("claiming", "archiving", "failing"):
            self.reconcile_moves(row)
        elif state == "claimed":
            if row["original_mode"] and not ready(Path(row["current"])):
                self.update(ident, state="integrity_failed", error="Original is not a hydrated regular file")
                return
            if digest(Path(row["current"])) != row["fingerprint"]:
                self.fail(row, "claimed source changed before upload")
                return
            config = request("GET", "/api/config")
            if config.get("fixedBandPolicy") is not True or (not row["clip_range"] and config.get("fixedBandAuto") is not True):
                raise RuntimeError("fixed-band policy or automatic selector unavailable")
            # A crash while uploading is safe to retry manually, not silently.
            self.update(ident, state="uploading")
            try:
                if row["clip_range"]:
                    session = self.prepare_range(Path(row["current"]))
                    start, end = json.loads(row["clip_range"])
                    payload = {"thumbnail_session_id": session, "selected_clips": [{"start": start, "end": end, "title": "Selected clip", "description": "Explicit source range"}], "acknowledged": True, "captions": False, "auto_hook": False}
                elif row["handoff"]:
                    if not config.get("localIntake"):
                        raise RuntimeError("local intake unavailable")
                    source = Path(row["current"])
                    stage = LOCAL_INBOX / row["handoff"]
                    if row["original_mode"]:
                        if not ready(source):
                            raise RuntimeError("original source unavailable")
                    elif stage.exists():
                        if not os.path.samefile(stage, source):
                            raise RuntimeError("local handoff collision")
                    else:
                        os.link(source, stage)
                    slot = request("POST", "/api/local-intake", {"capability": stage.stem, "extension": stage.suffix,
                                   "sha256": row["fingerprint"], "size": source.stat().st_size,
                                   "original": bool(row["original_mode"])}, timeout=3600, local_auth=True)
                    payload = {"upload_id": slot["upload_id"], "acknowledged": True}
                else:
                    slot = request("POST", "/api/uploads", {"filename": Path(row["original"]).name})
                    self.upload(Path(row["current"]), slot["upload_url"])
                    payload = {"upload_id": slot["upload_id"], "acknowledged": True}
            except Exception as exc:
                self.fail(row, f"upload failed: {exc}")
                return
            self.update(ident, state="submitting")
            try:
                result = request("POST", "/api/process", payload, local_auth=bool(row["handoff"]))
            except urllib.error.HTTPError as exc:
                detail = f"submission HTTP {exc.code}: {exc.read(500).decode(errors='replace')}"
                if exc.code >= 500:
                    self.update(ident, state="unknown_submission", error=detail)
                else:
                    self.fail(row, detail)
                return
            except Exception as exc:
                self.update(ident, state="unknown_submission", error=f"Submission outcome unknown: {exc}")
                return
            if not result.get("job_id"):
                self.update(ident, state="unknown_submission", error="Submission response has no job ID")
                return
            self.update(ident, state="running", job_id=result["job_id"])
        elif state == "running":
            try:
                result = request("GET", "/api/status/" + row["job_id"])
            except urllib.error.HTTPError as exc:
                if row["original_mode"] and exc.code == 404:
                    self.update(ident, state="interrupted", error="Backend job unavailable; reconcile manually")
                    return
                raise
            if result.get("status") == "failed":
                self.fail(row, "backend failed: " + str(result.get("logs", [])[-5:]))
            elif result.get("status") == "completed":
                clips = (result.get("result") or {}).get("clips") or []
                if not clips:
                    self.fail(row, "backend completed with no clips")
                    return
                self.update(ident, state="exporting", clips=json.dumps(clips))
        elif state == "exporting":
            folder = self.root / "clips" / ident
            folder.mkdir(exist_ok=True)
            receipts = []
            for i, clip in enumerate(json.loads(row["clips"])):
                url = clip.get("download_url") or clip.get("video_url")
                if not isinstance(url, str) or not url.startswith("/videos/" + row["job_id"] + "/"):
                    raise RuntimeError("unexpected artifact URL")
                target = folder / f"clip-{i + 1}.mp4"
                receipt = folder / f"clip-{i + 1}.json"
                temp = folder / f".clip-{i + 1}.part"
                if not target.exists() and temp.exists() and receipt.exists():
                    record = json.loads(receipt.read_text(encoding="utf-8"))
                    if temp.stat().st_size != record["bytes"] or digest(temp) != record["sha256"]:
                        raise RuntimeError("partial export differs from verified receipt")
                    move_no_replace(temp, target)
                if not target.exists():
                    with urllib.request.urlopen(BASE + url, timeout=300) as response, open(temp, "wb") as out:
                        shutil.copyfileobj(response, out, 1024 * 1024)
                        expected = response.headers.get("Content-Length")
                    if expected is None or temp.stat().st_size != int(expected):
                        raise RuntimeError("artifact transfer length cannot be verified")
                    if temp.stat().st_size == 0:
                        raise RuntimeError("empty clip")
                    ffmpeg = shutil.which("ffmpeg") or r"C:\Program Files\Streamlabs OBS\resources\app.asar.unpacked\node_modules\obs-studio-node\ffmpeg.exe"
                    check = subprocess.run([ffmpeg, "-v", "error", "-i", str(temp), "-f", "null", "-"], capture_output=True)
                    if check.returncode:
                        raise RuntimeError("artifact media decode failed")
                    record = {"sha256": digest(temp), "bytes": temp.stat().st_size}
                    receipt_temp = receipt.with_suffix(".json.part")
                    with receipt_temp.open("w", encoding="utf-8") as out:
                        json.dump(record, out)
                        out.flush()
                        os.fsync(out.fileno())
                    os.replace(receipt_temp, receipt)
                    move_no_replace(temp, target)
                if not receipt.exists():
                    raise RuntimeError("existing clip has no verified receipt")
                record = json.loads(receipt.read_text(encoding="utf-8"))
                if target.stat().st_size != record["bytes"] or digest(target) != record["sha256"]:
                    raise RuntimeError("clip differs from verified receipt")
                receipts.append({"path": str(target), "sha256": digest(target), "bytes": target.stat().st_size})
            if row["original_mode"]:
                if not ready(Path(row["current"])) or digest(Path(row["current"])) != row["fingerprint"]:
                    self.update(ident, state="integrity_failed", error="Original changed before completion")
                    return
                self.update(ident, clips=json.dumps(receipts), state="completed")
                return
            src = Path(row["current"])
            original = Path(row["original"])
            dest = self.root / "processed" / (original.stem + "_done" + original.suffix)
            if dest.exists():
                dest = self.root / "processed" / (original.stem + "_" + ident + "_done" + original.suffix)
            self.update(ident, clips=json.dumps(receipts), state="archiving", planned=str(dest))
            self.reconcile_moves(next(r for r in self.rows() if r["id"] == ident))
        elif state in ("uploading", "submitting"):
            self.update(ident, state="unknown_submission" if state == "submitting" else "interrupted_upload", error="Interrupted during " + state + "; manual review required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Dedicated incoming folder")
    parser.add_argument("action", choices=["watch", "once", "status", "retry"])
    parser.add_argument("--id", help="Local job ID for retry")
    parser.add_argument("--file", help="Root-level filename to process with once")
    parser.add_argument("--local-intake", action="store_true", help="Use same-volume, read-only local handoff for automatic jobs")
    parser.add_argument("--original", help="One hydrated original, bound read-only at the fixed server path")
    parser.add_argument("--stable-seconds", type=float, default=30)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--clip-range", nargs=2, type=float, metavar=("START", "END"), help="Explicit source seconds (5–180 seconds); bypass automatic selection")
    args = parser.parse_args()
    if args.stable_seconds < 0 or args.interval <= 0:
        parser.error("invalid timing")
    if args.clip_range and (args.clip_range[0] < 0 or not 5 <= args.clip_range[1] - args.clip_range[0] <= 180):
        parser.error("clip range must start at or after zero and last 5–180 seconds")
    if args.file and (args.action != "once" or Path(args.file).name != args.file):
        parser.error("--file requires once and a root-level filename")
    if args.local_intake and args.clip_range:
        parser.error("local intake currently supports automatic selection only")
    if args.original and (not args.local_intake or args.clip_range or args.action != "once" or args.file):
        parser.error("--original requires --local-intake once and no --file or --clip-range")
    root = Path(args.root).resolve(strict=True)
    lock_path = root / ".local-clipper.lock"
    with open(lock_path, "a+b") as lock:
        if os.name != "nt":
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SystemExit("Another worker holds the lock")
        w = Worker(root, args.stable_seconds, args.clip_range, args.local_intake, args.original)
        if args.action == "status":
            for row in w.rows():
                entry = dict(row)
                entry.pop("handoff", None)
                print(json.dumps(entry))
            return
        if args.action == "retry":
            try:
                w.retry(args.id)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
        if args.action == "once":
            w.scan(args.file)
            time.sleep(args.stable_seconds)
            args.id = w.scan(args.file)
            if not args.id:
                return
        while True:
            rows = [r for r in w.rows() if r["state"] in ("claiming", "claimed", "uploading", "submitting", "running", "exporting", "archiving", "failing")]
            if args.action in ("retry", "once"):
                rows = [r for r in rows if r["id"] == args.id]
                if not rows:
                    break
            try:
                if rows:
                    w.step(rows[0])
                else:
                    w.scan()
            except Exception as exc:
                print(f"Paused for retry/reconciliation: {exc}", file=sys.stderr)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
