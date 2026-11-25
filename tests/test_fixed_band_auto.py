"""Fixed band graph keeps source and camera in separate aspect-fit bands."""
import subprocess
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import app
import camera_inset


class FixedBandTests(unittest.TestCase):
    def test_resume_manifest_records_policy_and_reconstructs_env(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'job').mkdir()
            with patch.object(app, 'OUTPUT_DIR', temp):
                app._write_resume_manifest('job', ['main.py'], 2, None, None, False,
                                           fixed_band_policy='v1')
                manifest = json.loads(Path(temp, 'job', app._RESUME_FILE).read_text())
            self.assertEqual(manifest['fixed_band_policy'], 'v1')
            env = {'AUTO_CAPTIONS': '1', 'REFRAME_ENGINE': 'v1'}
            app._apply_fixed_band_policy(env)
            self.assertEqual(env['AUTO_CAPTIONS'], '0')
            self.assertEqual(env['AUTO_HOOK'], '0')
            self.assertEqual(env['REFRAME_ENGINE'], 'v2')
            self.assertEqual(env['FIXED_BAND_LAYOUT'], '1')

    def test_resume_applies_policy_and_rejects_unknown_marker(self):
        manifest = {'fixed_band_policy': 'v1', 'cmd': ['main.py'], 'priority': 2}
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'OUTPUT_DIR', temp), \
             patch.object(app, '_enqueue_job'), patch.object(app.remote_worker, 'clear'):
            try:
                self.assertEqual(app._register_resumed([('test-resume-fixed', manifest)]), 1)
                env = app.jobs['test-resume-fixed']['env']
                self.assertEqual(env['FIXED_BAND_LAYOUT'], '1')
                self.assertEqual(env['AUTO_CAPTIONS'], '0')
                self.assertEqual(env['AUTO_HOOK'], '0')
                self.assertEqual(env['REFRAME_ENGINE'], 'v2')
                self.assertEqual(app._register_resumed([('test-resume-unknown', {'fixed_band_policy': 'v9'})]), 0)
                self.assertNotIn('test-resume-unknown', app.jobs)
            finally:
                app.jobs.pop('test-resume-fixed', None)

    def test_composite_and_vertical_sources_encode(self):
        for width, height, box in ((640, 360, (0, 0, 180, 120)),
                                   (360, 640, (10, 10, 100, 120))):
            with self.subTest(width=width):
                graph = camera_inset.inset_filtergraph(width, height, 360, 640, box, fixed=True)
                self.assertIn('force_original_aspect_ratio=decrease', graph)
                self.assertNotIn('crop=w=', graph)
                result = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                         f'testsrc2=size={width}x{height}:rate=1',
                                         '-filter_complex', graph, '-map', '[v]', '-frames:v', '1',
                                         '-f', 'null', '-'], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
