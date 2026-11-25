"""Source lookup remains available when new uploads move to another volume."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class LegacyUploadTests(unittest.TestCase):
    def test_new_upload_preferred_and_legacy_available(self):
        with tempfile.TemporaryDirectory() as temp:
            new, legacy = Path(temp) / "new", Path(temp) / "legacy"
            new.mkdir()
            legacy.mkdir()
            with patch.object(app, "UPLOAD_DIR", str(new)), patch.object(app, "LEGACY_UPLOAD_DIR", str(legacy)):
                old_source = legacy / "job_source.mp4"
                old_source.write_bytes(b"legacy")
                self.assertEqual(app._locate_source("job"), str(old_source))
                new_source = new / "job_source.mp4"
                new_source.write_bytes(b"new")
                self.assertEqual(app._locate_source("job"), str(new_source))
                self.assertEqual(old_source.read_bytes(), b"legacy")


if __name__ == "__main__":
    unittest.main()
