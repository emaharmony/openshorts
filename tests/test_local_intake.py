import hashlib
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app


class LocalIntakeTests(unittest.TestCase):
    def test_original_resume_manifest_is_not_mutated_or_requeued(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp, 'resume.json')
            original = {'cmd': ['python', 'main.py', '-i', '/data/original/source.mp4'], 'attempts': 99, 'run_started': 10}
            manifest.write_text(json.dumps(original), encoding='utf-8')
            with patch.object(app, '_manifest_names', return_value=['fixture']), patch.object(app, '_manifest_path', return_value=str(manifest)):
                _, picked = app._resume_candidates(set(), 100)
            self.assertEqual(picked, [])
            self.assertEqual(json.loads(manifest.read_text()), original)

    def test_put_cannot_write_local_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, 'source.mp4'); source.write_bytes(b'original')
            app.pending_uploads['readonly-test'] = {'path': str(source), 'created': app.time.time(), 'local_readonly': True}
            try:
                with self.assertRaises(app.HTTPException) as error:
                    asyncio.run(app.put_upload('readonly-test', SimpleNamespace()))
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(source.read_bytes(), b'original')
            finally:
                app.pending_uploads.pop('readonly-test', None)
    def test_separate_token_required(self):
        with tempfile.TemporaryDirectory() as temp:
            token = Path(temp, 'token')
            token.write_text('a' * 64)
            with patch.object(app, 'LOCAL_INTAKE_TOKEN_FILE', str(token)):
                app._authorize_local_intake(SimpleNamespace(headers={'x-openshorts-local-token': 'a' * 64}))
                with self.assertRaises(app.HTTPException):
                    app._authorize_local_intake(SimpleNamespace(headers={'x-openshorts-local-token': 'b' * 64}))

    def test_fingerprint_and_path_guards(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'LOCAL_INBOX', temp):
            capability = 'a' * 64
            source = Path(temp, capability + '.mp4')
            source.write_bytes(b'content')
            sha = hashlib.sha256(b'content').hexdigest()
            path, identity = app._inspect_local_handoff(capability, '.mp4', sha, 7)
            self.assertEqual(path, str(source))
            self.assertEqual(identity[2], 7)
            for bad in ('../secret', 'x' * 64, capability + '/x'):
                with self.assertRaises(ValueError):
                    app._inspect_local_handoff(bad, '.mp4', sha, 7)
            with self.assertRaises(ValueError):
                app._inspect_local_handoff(capability, '.mp4', 'b' * 64, 7)
            with self.assertRaises(ValueError):
                app._inspect_local_handoff(capability, '.mp4', sha, 8)
            link = Path(temp, 'b' * 64 + '.mkv')
            os.symlink(source, link)
            with self.assertRaises(OSError):
                app._inspect_local_handoff('b' * 64, '.mkv', sha, 7)

    def test_local_rejection_never_deletes_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, 'source')
            source.write_bytes(b'content')
            app._discard_rejected_source(str(source), None, {'local_readonly': True}, 'id')
            self.assertEqual(source.read_bytes(), b'content')

    def test_history_fails_closed_if_handoff_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inbox, uploads = root / 'inbox', root / 'uploads'
            inbox.mkdir(); uploads.mkdir()
            index = uploads / '.local-source-index'
            index.mkdir()
            name = 'd' * 64 + '.mp4'
            path = inbox / name
            path.write_bytes(b'original')
            st = path.stat()
            ident = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
            job = '12345678-1234-4234-8234-123456789abc'
            (index / (job + '.json')).write_text(json.dumps({'name': name, 'identity': ident}))
            with patch.object(app, 'LOCAL_INBOX', str(inbox)), patch.object(app, 'UPLOAD_DIR', str(uploads)), \
                 patch.object(app, 'LEGACY_UPLOAD_DIR', str(root / 'legacy')), patch.object(app, 'OUTPUT_DIR', str(root / 'output')):
                self.assertEqual(app._locate_source(job), str(path))
                path.write_bytes(b'changed payload')
                self.assertIsNone(app._locate_source(job))

    def test_replay_is_rejected_and_expired_slot_is_not_consumed(self):
        class Request:
            headers = {'x-openshorts-local-token': 'a' * 64}
            async def json(self):
                return {'capability': 'b' * 64, 'extension': '.mp4',
                        'sha256': hashlib.sha256(b'content').hexdigest(), 'size': 7}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ('b' * 64 + '.mp4')).write_bytes(b'content')
            token = root / 'token'
            token.write_text('a' * 64)
            with patch.object(app, 'LOCAL_INBOX', temp), patch.object(app, 'UPLOAD_DIR', temp), \
                 patch.object(app, 'LOCAL_INTAKE_TOKEN_FILE', str(token)), \
                 patch.object(app, 'BILLING_ENABLED', False), patch.dict(os.environ, {'OPENSHORTS_LOCAL_INTAKE': '1'}), \
                 patch.object(app, '_owner_id', return_value=None):
                first = asyncio.run(app.local_intake(Request()))
                try:
                    with self.assertRaises(app.HTTPException) as error:
                        asyncio.run(app.local_intake(Request()))
                    self.assertEqual(error.exception.status_code, 409)
                    app.pending_uploads[first['upload_id']]['created'] = 0
                    with self.assertRaises(app.HTTPException):
                        app._take_pending_upload(first['upload_id'], None)
                finally:
                    app.pending_uploads.pop(first['upload_id'], None)


if __name__ == '__main__':
    unittest.main()
