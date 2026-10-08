# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests for tools/fork/check.py.
"""Run with: python3 -m unittest discover -s tools/fork/tests"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FORK_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FORK_DIR))

import check  # noqa: E402

SPDX_PY = "# SPDX-License-Identifier: LGPL-2.1-or-later\n"
SPDX_CPP = "// SPDX-License-Identifier: LGPL-2.1-or-later\n"


class TempRepo:
    """A git repository with the fork config files and one upstream commit."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="forkcheck-"))
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        cfg = self.dir / "tools/fork"
        cfg.mkdir(parents=True)
        for name in ("fork_paths.txt", "reserved_terms.txt", "data_licenses.txt"):
            shutil.copy(FORK_DIR / name, cfg / name)
        (cfg / "dependencies.json").write_text(
            json.dumps(
                {
                    "_comment": "SPDX-License-Identifier: LGPL-2.1-or-later",
                    "dependencies": [
                        {"name": "zlib", "version": "build", "license": "Zlib",
                         "linkage": "linked", "origin": "upstream", "url": "https://zlib.net"}
                    ],
                }
            )
        )
        self.write("src/Gui/Upstream.cpp", "int a = 0;\n")
        self.write("src/Mod/Upstream/Net.py", "import socket\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "upstream")
        base = self.git("rev-parse", "HEAD").strip()
        (cfg / "UPSTREAM_BASE").write_text(base + "\n")
        self.repo = check.Repo(self.dir)
        deps = check.load_deps(self.repo)
        (self.dir / "THIRD_PARTY_LICENSES").write_text(check.render_third_party(deps))

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True, text=True).stdout

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def run(self, name):
        scope = check.build_scope(self.repo)
        return check.CHECKS[name](self.repo, scope)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.t = TempRepo()

    def tearDown(self):
        self.t.cleanup()


class NetworkTest(Base):
    def test_clean_repo_passes(self):
        self.assertEqual(self.t.run("network"), [])

    def test_inherited_network_code_is_ignored(self):
        # src/Mod/Upstream/Net.py imports socket but is unchanged upstream code.
        self.assertEqual(self.t.run("network"), [])

    def test_fork_owned_python_flagged(self):
        self.t.write("src/Mod/Construction/x.py", SPDX_PY + "import requests\n")
        f = self.t.run("network")
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0].path, f[0].line), ("src/Mod/Construction/x.py", 2))

    def test_urllib_parse_allowed(self):
        self.t.write("src/Mod/Construction/x.py", SPDX_PY + "from urllib.parse import quote\n")
        self.assertEqual(self.t.run("network"), [])

    def test_urllib_request_flagged(self):
        self.t.write("src/Mod/Construction/x.py", SPDX_PY + "from urllib import request\n")
        self.assertEqual(len(self.t.run("network")), 1)

    def test_fork_owned_cpp_flagged(self):
        self.t.write("src/Gui/Hotkeys/x.cpp", SPDX_CPP + "QNetworkAccessManager m;\n")
        self.assertEqual(len(self.t.run("network")), 1)

    def test_added_line_in_upstream_file_flagged(self):
        self.t.write("src/Gui/Upstream.cpp", "int a = 0;\n// FORK: x\nQTcpSocket s;\n")
        f = self.t.run("network")
        self.assertEqual([(x.path, x.line) for x in f], [("src/Gui/Upstream.cpp", 3)])


class TermsTest(Base):
    def test_term_in_cpp_string_flagged(self):
        self.t.write("src/Gui/Hotkeys/x.cpp", SPDX_CPP + 'auto s = QObject::tr("Open Toolbox");\n')
        f = self.t.run("terms")
        self.assertEqual(len(f), 1)
        self.assertIn("Toolbox", f[0].message)

    def test_term_in_cpp_comment_ignored(self):
        self.t.write("src/Gui/Hotkeys/x.cpp", SPDX_CPP + '// not a Toolbox\nauto s = "ok";\n')
        self.assertEqual(self.t.run("terms"), [])

    def test_separator_variants(self):
        for s in ("PushPull", "push-pull", "Push/Pull", "push pull"):
            with self.subTest(s=s):
                self.t.write("src/Mod/Construction/x.py", SPDX_PY + f"name = '{s}'\n")
                self.assertEqual(len(self.t.run("terms")), 1)

    def test_word_boundary(self):
        self.t.write("src/Mod/Construction/x.py", SPDX_PY + "name = 'asynchronous'\n")
        self.assertEqual(self.t.run("terms"), [])

    def test_python_identifier_not_flagged(self):
        self.t.write("src/Mod/Construction/x.py", SPDX_PY + "Toolbox = 1\n")
        self.assertEqual(self.t.run("terms"), [])


class DataTest(Base):
    def lib(self, items):
        self.t.write("src/Mod/Construction/Resources/libraries/US/lumber.json", json.dumps(items))

    def test_valid_entry(self):
        self.lib([{"id": "a", "source": "PS 20", "data_license": "public-domain"}])
        self.assertEqual(self.t.run("data"), [])

    def test_missing_fields(self):
        self.lib([{"id": "a"}])
        self.assertEqual(len(self.t.run("data")), 2)

    def test_bad_license(self):
        self.lib({"items": [{"id": "a", "source": "x", "data_license": "proprietary"}]})
        f = self.t.run("data")
        self.assertEqual(len(f), 1)
        self.assertIn("allowlist", f[0].message)

    def test_file_level_defaults(self):
        self.lib({"source": "PS 20", "data_license": "CC0-1.0", "items": [{"id": "a"}]})
        self.assertEqual(self.t.run("data"), [])


class HeadersTest(Base):
    def test_missing_spdx(self):
        self.t.write("src/Mod/Construction/x.py", "print(1)\n")
        f = self.t.run("headers")
        self.assertEqual([x.path for x in f], ["src/Mod/Construction/x.py"])

    def test_upstream_edit_needs_marker(self):
        self.t.write("src/Gui/Upstream.cpp", "int a = 1;\n")
        self.assertEqual(len(self.t.run("headers")), 1)
        self.t.write("src/Gui/Upstream.cpp", "int a = 1;  // FORK: changed\n")
        self.assertEqual(self.t.run("headers"), [])


class DepsTest(Base):
    def set_deps(self, deps):
        p = self.t.dir / "tools/fork/dependencies.json"
        p.write_text(json.dumps({"dependencies": deps}))
        (self.t.dir / "THIRD_PARTY_LICENSES").write_text(check.render_third_party(deps))

    def dep(self, **kw):
        d = {"name": "x", "version": "1", "license": "MIT", "linkage": "linked",
             "origin": "fork", "url": "https://example.invalid"}
        d.update(kw)
        return d

    def test_ok(self):
        self.assertEqual(self.t.run("deps"), [])

    def test_gpl_linked_rejected(self):
        self.set_deps([self.dep(license="GPL-3.0-or-later")])
        self.assertEqual(len(self.t.run("deps")), 1)

    def test_gpl_external_allowed(self):
        self.set_deps([self.dep(license="GPL-2.0-only", linkage="external")])
        self.assertEqual(self.t.run("deps"), [])

    def test_unknown_license_rejected(self):
        self.set_deps([self.dep(license="LicenseRef-Proprietary")])
        self.assertEqual(len(self.t.run("deps")), 1)

    def test_stale_third_party_file(self):
        (self.t.dir / "THIRD_PARTY_LICENSES").write_text("old\n")
        f = self.t.run("deps")
        self.assertEqual([x.path for x in f], ["THIRD_PARTY_LICENSES"])


class LexerTest(unittest.TestCase):
    def test_cpp_strings(self):
        src = 'a("x\\"y"); /* "no" */ b(R"d(raw "q")d"); c(\'"\');\n// "no"\nd("z");'
        self.assertEqual([s for _, s in check.cpp_strings(src)], ['x\\"y', 'raw "q"', "z"])
        self.assertEqual(check.cpp_strings(src)[-1][0], 3)

    def test_glob(self):
        ps = check.PathSet(["src/Gui/Hotkeys/**", "docs/*.md"])
        self.assertIn("src/Gui/Hotkeys/a/b.cpp", ps)
        self.assertIn("docs/a.md", ps)
        self.assertNotIn("docs/x/a.md", ps)
        self.assertNotIn("src/Gui/Hotkey.cpp", ps)


if __name__ == "__main__":
    unittest.main()
