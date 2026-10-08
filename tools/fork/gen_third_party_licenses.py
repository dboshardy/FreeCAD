#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: regenerates THIRD_PARTY_LICENSES from tools/fork/dependencies.json.
"""Write THIRD_PARTY_LICENSES from tools/fork/dependencies.json."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check  # noqa: E402


def main() -> int:
    repo = check.default_repo()
    text = check.render_third_party(check.load_deps(repo))
    (repo.root / "THIRD_PARTY_LICENSES").write_text(text, encoding="utf-8")
    print(f"wrote {repo.root / 'THIRD_PARTY_LICENSES'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
