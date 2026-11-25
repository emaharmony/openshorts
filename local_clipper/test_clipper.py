import tempfile
import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from clipper import Worker, digest, move_no_replace


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('clipper.request', return_value={'fixedBandPolicy': True, 'fixedBandAuto': True})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_original_is_not_moved_and_failure_preserves_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, 'state'); root.mkdir()
            source = Path(temp, 'original.mp4'); source.write_bytes(b'fixture')
            with patch('clipper.LOCAL_TOKEN') as token, patch('clipper.LOCAL_INBOX') as inbox:
                token.is_file.return_value = True; inbox.is_dir.return_value = True
                with patch('clipper.request', return_value={'fixedBandPolicy': True, 'fixedBandAuto': True, 'localIntake': True}):
                    w = Worker(root, 0, local_intake=True, original=source)
                    w.scan(); ident = w.scan()
                row = w.rows()[0]
                self.assertEqual(row['state'], 'claimed')
                self.assertTrue(source.exists())
                w.fail(row, 'fixture failure')
                self.assertEqual(w.rows()[0]['state'], 'failed')
                self.assertEqual(source.read_bytes(), b'fixture')
                w.db.close()

    def test_original_missing_backend_job_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, 'state'); root.mkdir()
            source = Path(temp, 'original.mp4'); source.write_bytes(b'fixture')
            w = Worker(root, 0, local_intake=True, original=source)
            w.db.execute("INSERT INTO jobs (id,original,current,fingerprint,state,updated,job_id,original_mode) VALUES (?,?,?,?, 'running',0,'missing',1)", ('id', str(source), str(source), digest(source)))
            w.db.commit()
            error = urllib.error.HTTPError('http://localhost', 404, 'missing', {}, None)
            with patch('clipper.request', side_effect=error):
                w.step(w.rows()[0])
            self.assertEqual(w.rows()[0]['state'], 'interrupted')
            self.assertEqual(source.read_bytes(), b'fixture')
            w.db.close()
    def test_readiness_duplicate_and_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'a.mkv'
            source.write_bytes(b'video')
            w = Worker(root, 0, [0, 8])
            self.assertIsNone(w.scan())
            ident = w.scan()
            row = w.rows()[0]
            self.assertEqual(row['state'], 'claimed')
            self.assertEqual(Path(row['current']).suffix, '.mkv')
            (root / 'duplicate.mp4').write_bytes(b'video')
            w.scan()
            self.assertIsNone(w.scan())
            self.assertTrue((root / 'duplicate.mp4').exists())
            w.db.close()
            recovered = Worker(root, 0)
            self.assertEqual(recovered.rows()[0]['id'], ident)
            recovered.db.close()

    def test_no_overwrite_and_interrupted_move(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, dst = root / 'a', root / 'b'
            src.write_bytes(b'a')
            dst.write_bytes(b'b')
            with self.assertRaises(FileExistsError):
                move_no_replace(src, dst)
            self.assertEqual(dst.read_bytes(), b'b')
            w = Worker(root, 0)
            claimed = root / 'working' / 'job.mp4'
            source = root / 'x.mp4'
            source.write_bytes(b'x')
            w.db.execute("INSERT INTO jobs (id,original,current,planned,fingerprint,state,updated) VALUES ('job',?,?,?,?, 'claiming', 0)", (str(source), str(source), str(claimed), digest(source)))
            w.db.commit()
            w.reconcile_moves(w.rows()[0])
            self.assertEqual(w.rows()[0]['state'], 'claimed')
            self.assertTrue(claimed.exists())
            w.db.close()

    def test_rejection_preserves_source_and_ambiguous_submission_pauses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'x.mp4').write_bytes(b'x')
            w = Worker(root, 0, [0, 8])
            w.scan(); w.scan()
            row = w.rows()[0]
            with patch.object(w, 'prepare_range', return_value='session'), patch('clipper.request', side_effect=[{'fixedBandPolicy': True}, TimeoutError('lost reply')]):
                w.step(row)
            self.assertEqual(w.rows()[0]['state'], 'unknown_submission')
            self.assertTrue(Path(w.rows()[0]['current']).exists())
            w.db.close()

    def test_http_500_is_ambiguous_and_restart_polls_known_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'x.mp4').write_bytes(b'x')
            w = Worker(root, 0, [0, 8])
            w.scan(); w.scan()
            row = w.rows()[0]
            error = urllib.error.HTTPError('http://localhost', 500, 'error', {}, None)
            with patch.object(w, 'prepare_range', return_value='session'), patch('clipper.request', side_effect=[{'fixedBandPolicy': True}, error]):
                w.step(row)
            self.assertEqual(w.rows()[0]['state'], 'unknown_submission')
            w.update(row['id'], state='running', job_id='known')
            w.db.close()
            w = Worker(root, 0)
            with patch('clipper.request', return_value={'status': 'processing'}) as call:
                w.step(w.rows()[0])
            self.assertEqual(call.call_args.args[1], '/api/status/known')
            self.assertEqual(w.rows()[0]['state'], 'running')
            w.db.close()

    def test_local_handoff_uses_hardlink_and_no_upload_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, 'root')
            inbox = Path(temp, 'inbox')
            root.mkdir(); inbox.mkdir()
            source = root / 'pilot.mp4'
            source.write_bytes(b'fixture')
            with patch('clipper.LOCAL_INBOX', inbox), patch('clipper.LOCAL_TOKEN') as token:
                token.is_file.return_value = True
                w = Worker(root, 0, local_intake=True)
                with patch('clipper.request', return_value={'fixedBandPolicy': True, 'fixedBandAuto': True, 'localIntake': True}):
                    w.scan(); w.scan()
                row = w.rows()[0]
                responses = [{'fixedBandPolicy': True, 'fixedBandAuto': True, 'localIntake': True}, {'upload_id': 'slot'}, {'job_id': 'job'}]
                with patch('clipper.request', side_effect=responses) as call, patch.object(w, 'upload') as upload:
                    w.step(row)
                upload.assert_not_called()
                self.assertTrue(os.path.samefile(inbox / row['handoff'], row['current']))
                self.assertEqual(w.rows()[0]['job_id'], 'job')
                self.assertTrue(call.call_args.kwargs['local_auth'])
                Path(row['current']).write_bytes(b'changed')
                w.step(w.rows()[0])
                self.assertEqual(w.rows()[0]['state'], 'integrity_failed')
                self.assertTrue(Path(row['current']).exists())
                w.db.close()

    def test_retry_rotates_consumed_locator_and_rejects_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            w = Worker(Path(temp), 0)
            w.db.execute("INSERT INTO jobs (id,current,handoff,state,retries,updated) VALUES (?,?,?,?,0,0)",
                         ('job', str(Path(temp) / 'source.mkv'), 'a' * 64 + '.mkv', 'failed'))
            w.db.commit()
            w.retry('job')
            row = w.rows()[0]
            self.assertEqual(row['state'], 'claimed')
            self.assertNotEqual(row['handoff'], 'a' * 64 + '.mkv')
            self.assertTrue(row['handoff'].endswith('.mkv'))
            self.assertEqual(row['retries'], 1)
            w.update('job', state='unknown_submission')
            with self.assertRaises(ValueError):
                w.retry('job')
            w.db.close()


if __name__ == '__main__':
    unittest.main()
