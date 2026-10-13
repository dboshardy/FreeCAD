#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Add-on compliance checks (design doc §1, §12 R21): network APIs and SPDX headers.

Usage: python3 check.py [network|headers|all] [root]   (root defaults to this folder)
"""
# shortcut: only network and headers; reserved terms, data licences and dependency
# checks still live in tools/fork/check.py. Port them when the first add-on is split out.

import re
import sys
from pathlib import Path

NETWORK = re.compile(
    r"\bQNetwork\w*\b|\bQTcpSocket\b|\bQUdpSocket\b|\bQSslSocket\b|\bQWebSocket\w*\b|\bQWebEngine\w*\b"
    r"|\bcurl_easy_\w+|\bgetaddrinfo\s*\(|\bgethostbyname\s*\(|<sys/socket\.h>|<winsock2?\.h>"
    r"|\bQDesktopServices::openUrl\b"
    r"|^\s*(?:import|from)\s+(?:urllib|requests|http\.client|socket|ftplib|smtplib|xmlrpc|httpx|aiohttp)\b"
)
CODE = {".py", ".c", ".cc", ".cpp", ".h", ".hpp"}
HEADED = CODE | {".md", ".xml", ".yml", ".yaml", ".cmake"}
SKIP = {"check.py", "test_check.py"}  # contain the patterns as data
SKIP_DIRS = {".git", "__pycache__"}


def files(root):
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and not SKIP_DIRS & set(p.parts):
            yield p


def check_network(root):
    out = []
    for p in files(root):
        if p.suffix not in CODE or p.name in SKIP:
            continue
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if NETWORK.search(line):
                out.append(f"{p}:{n}: network API: {line.strip()}")
    return out


def check_headers(root):
    out = []
    for p in files(root):
        if p.suffix in HEADED and "SPDX-License-Identifier" not in "\n".join(
            p.read_text(errors="replace").splitlines()[:12]
        ):
            out.append(f"{p}: missing SPDX-License-Identifier in the first 12 lines")
    return out


def main(argv):
    which = argv[1] if len(argv) > 1 else "all"
    root = argv[2] if len(argv) > 2 else Path(__file__).parent
    problems = []
    if which in ("network", "all"):
        problems += check_network(root)
    if which in ("headers", "all"):
        problems += check_headers(root)
    print("\n".join(problems) or "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
