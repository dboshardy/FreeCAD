# SPDX-License-Identifier: LGPL-2.1-or-later
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import check


class TestCheck(unittest.TestCase):
    def test_flags_network_and_missing_header(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("import requests\n")
            self.assertEqual(len(check.check_network(d)), 1)
            self.assertEqual(len(check.check_headers(d)), 1)
            (Path(d) / "a.py").write_text("# SPDX-License-Identifier: LGPL-2.1-or-later\nx = 1\n")
            self.assertEqual(check.check_network(d) + check.check_headers(d), [])

    def test_template_is_clean(self):
        root = Path(__file__).parent.parent
        self.assertEqual(check.check_network(root) + check.check_headers(root), [])


if __name__ == "__main__":
    unittest.main()
