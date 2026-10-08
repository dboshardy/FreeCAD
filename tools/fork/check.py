#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: compliance checks for the CADApp fork (design doc §1, §9, §12 R18, R21, R23).
"""Fork compliance checks.

Subcommands:
  network     Network APIs in fork-added code (design doc §1).
  terms       Reserved terms in fork-added UI strings (§12 R21).
  data        source/data_license on shipped library data (§9, §12 R13).
  headers     SPDX headers on fork-owned files; FORK: markers in edited upstream files.
  deps        Dependency licenses and linkage (§1, §12 R23); THIRD_PARTY_LICENSES up to date.
  inventory   Report reserved terms in inherited upstream UI strings (no failure).
  all         network, terms, data, headers, deps.

"Fork-added code" is every file matching tools/fork/fork_paths.txt plus the lines
added to other files since the commit in tools/fork/UPSTREAM_BASE. When that commit
is not available (shallow clone), only fork-owned files are checked and a warning is
printed.

Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Files that contain the checked patterns as data and are therefore not scanned
# by the pattern-based checks (they are still covered by the header check).
SELF_EXEMPT = (
    "tools/fork/check.py",
    "tools/fork/reserved_terms.txt",
    "tools/fork/tests/**",
)

SOURCE_EXT = {".py", ".pyi", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".js", ".ts"}
CPP_EXT = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
PY_EXT = {".py", ".pyi"}

# Extensions that must carry an SPDX header when fork-owned. JSON cannot hold
# comments; JSON files carry it in a "_comment" or "_spdx" member instead.
HEADER_EXT = SOURCE_EXT | {".cmake", ".txt", ".md", ".yml", ".yaml", ".ui", ".qrc", ".svg", ".json", ".in"}
HEADER_EXEMPT_NAMES = {"UPSTREAM_BASE", "THIRD_PARTY_LICENSES"}
HEADER_LINES = 12

NETWORK_PATTERNS_CPP = [
    r"\bQNetworkAccessManager\b",
    r"\bQNetworkRequest\b",
    r"\bQNetworkReply\b",
    r"\bQTcpSocket\b",
    r"\bQTcpServer\b",
    r"\bQUdpSocket\b",
    r"\bQSslSocket\b",
    r"\bQWebSocket\w*\b",
    r"\bQHostInfo\b",
    r"\bQWebEngine\w*\b",
    r"\bQtNetwork\b",
    r"\bcurl_easy_\w+\b",
    r"\bgetaddrinfo\s*\(",
    r"\bgethostbyname\s*\(",
    r"#\s*include\s*<sys/socket\.h>",
    r"#\s*include\s*<winsock2?\.h>",
    r"\bQDesktopServices::openUrl\b",
]

NETWORK_PATTERNS_PY = [
    r"^\s*(?:import|from)\s+(?:requests|httpx|aiohttp|socket|ssl|ftplib|smtplib|poplib|imaplib|telnetlib|webbrowser|urllib2|urllib3|websocket|websockets|socketserver)\b",
    r"^\s*from\s+urllib\s+import\s+.*\brequest\b",
    r"\burllib\.request\b",
    r"\burlopen\s*\(",
    r"\bhttp\.client\b",
    r"\bhttp\.server\b",
    r"\bxmlrpc\.client\b",
    r"\bQtNetwork\b",
    r"\bQNetworkAccessManager\b",
    r"\bQDesktopServices\.openUrl\b",
]


# --------------------------------------------------------------------------- repo


@dataclass
class Repo:
    root: Path

    def git(self, *args: str, check: bool = True) -> str:
        res = subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=False
        )
        if check and res.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
        return res.stdout

    def files(self) -> list[str]:
        out = self.git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
        return sorted({p for p in out.split("\0") if p and (self.root / p).is_file()})

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8", errors="replace")


def default_repo() -> Repo:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True, text=True
    )
    return Repo(Path(out.stdout.strip()) if out.returncode == 0 else HERE.parent.parent)


def load_list(path: Path) -> list[str]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return items


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """fnmatch-style glob where '**' spans directories and '*' does not."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append(r"(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(r".*")
            i += 2
        elif pattern[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


class PathSet:
    def __init__(self, patterns: list[str] | tuple[str, ...]):
        self._regexes = [glob_to_regex(p) for p in patterns]

    def __contains__(self, rel: str) -> bool:
        return any(r.match(rel) for r in self._regexes)


def fork_paths(repo: Repo) -> PathSet:
    return PathSet(load_list(repo.root / "tools/fork/fork_paths.txt"))


def upstream_base(repo: Repo) -> str | None:
    base_file = repo.root / "tools/fork/UPSTREAM_BASE"
    if not base_file.exists():
        return None
    base = base_file.read_text(encoding="utf-8").strip()
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=repo.root, capture_output=True
    )
    return base if res.returncode == 0 else None


def added_lines(repo: Repo, base: str, owned: PathSet) -> dict[str, list[tuple[int, str]]]:
    """Lines added to non-fork-owned files since base (working tree included)."""
    out = repo.git("diff", "--no-color", "--unified=0", "--no-renames", base, "--")
    result: dict[str, list[tuple[int, str]]] = {}
    current = None
    lineno = 0
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            current = path[2:] if path.startswith("b/") else None
            if current is not None and current in owned:
                current = None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
        elif current and line.startswith("+"):
            result.setdefault(current, []).append((lineno, line[1:]))
            lineno += 1
    # untracked files outside fork paths are entirely "added"
    for rel in repo.git("ls-files", "-z", "--others", "--exclude-standard").split("\0"):
        if rel and rel not in owned and (repo.root / rel).is_file():
            text = repo.read(rel)
            result[rel] = list(enumerate(text.splitlines(), start=1))
    return result


def changed_upstream_files(repo: Repo, base: str, owned: PathSet) -> list[str]:
    out = repo.git("diff", "--name-only", "--diff-filter=M", "--no-renames", base, "--")
    return [p for p in out.splitlines() if p and p not in owned]


@dataclass
class Finding:
    check: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.check}] {self.message}"


@dataclass
class Scope:
    """Fork-added code: whole fork-owned files plus added lines in upstream files."""

    owned_files: list[str]
    upstream_lines: dict[str, list[tuple[int, str]]]
    base_available: bool


def build_scope(repo: Repo) -> Scope:
    owned = fork_paths(repo)
    exempt = PathSet(SELF_EXEMPT)
    files = [f for f in repo.files() if f in owned and f not in exempt]
    base = upstream_base(repo)
    lines = added_lines(repo, base, owned) if base else {}
    lines = {k: v for k, v in lines.items() if k not in exempt}
    return Scope(files, lines, base is not None)


def warn_no_base(scope: Scope) -> None:
    if not scope.base_available:
        print(
            "warning: tools/fork/UPSTREAM_BASE commit not available; edits to upstream "
            "files are not checked (fetch full history to enable)",
            file=sys.stderr,
        )


# ------------------------------------------------------------------------ network


def network_patterns(ext: str) -> list[re.Pattern[str]]:
    if ext in PY_EXT:
        pats = NETWORK_PATTERNS_PY
    elif ext in CPP_EXT:
        pats = NETWORK_PATTERNS_CPP
    else:
        pats = NETWORK_PATTERNS_CPP + NETWORK_PATTERNS_PY
    return [re.compile(p) for p in pats]


def scan_network_lines(path: str, lines: list[tuple[int, str]]) -> list[Finding]:
    ext = Path(path).suffix.lower()
    if ext not in SOURCE_EXT:
        return []
    findings = []
    for lineno, text in lines:
        for pat in network_patterns(ext):
            m = pat.search(text)
            if m:
                findings.append(
                    Finding("network", path, lineno, f"network API '{m.group(0).strip()}'")
                )
                break
    return findings


def check_network(repo: Repo, scope: Scope) -> list[Finding]:
    findings = []
    for rel in scope.owned_files:
        text = repo.read(rel)
        findings += scan_network_lines(rel, list(enumerate(text.splitlines(), start=1)))
    for rel, lines in scope.upstream_lines.items():
        findings += scan_network_lines(rel, lines)
    return findings


# -------------------------------------------------------------------------- terms


def term_regex(term: str) -> re.Pattern[str]:
    words = [w for w in re.split(r"[\s/_-]+", term) if w]
    sep = r"[\s/_-]?"
    return re.compile(r"(?<![A-Za-z0-9])" + sep.join(map(re.escape, words)) + r"(?![A-Za-z0-9])", re.I)


def reserved_terms(repo: Repo) -> list[tuple[str, re.Pattern[str]]]:
    return [(t, term_regex(t)) for t in load_list(repo.root / "tools/fork/reserved_terms.txt")]


def cpp_strings(text: str) -> list[tuple[int, str]]:
    """String literals in C/C++ source, skipping comments and char literals."""
    out = []
    i, n, line = 0, len(text), 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += text.count("\n", i, j)
            i = j
        elif c == "R" and text.startswith('R"', i) and (i == 0 or not text[i - 1].isalnum()):
            m = re.match(r'R"([^(\s]{0,16})\(', text[i:])
            if not m:
                i += 1
                continue
            end = ")" + m.group(1) + '"'
            start = i + m.end()
            j = text.find(end, start)
            j = n if j < 0 else j
            out.append((line, text[start:j]))
            line += text.count("\n", i, j)
            i = j + len(end)
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out.append((line, text[i + 1 : j]))
            i = j + 1
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'" and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        else:
            i += 1
    return out


def py_strings(text: str) -> list[tuple[int, str]]:
    out = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return [(i, l) for i, l in enumerate(text.splitlines(), start=1)]
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    for tok in tokens:
        if tok.type == tokenize.STRING or (fstring_middle is not None and tok.type == fstring_middle):
            out.append((tok.start[0], tok.string))
    return out


def json_strings(text: str) -> list[tuple[int, str]]:
    # Line numbers are approximate: report the line on which each string first occurs.
    out = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [(i, l) for i, l in enumerate(text.splitlines(), start=1)]

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if not k.startswith("_"):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            idx = text.find(json.dumps(node)[1:-1])
            out.append((text.count("\n", 0, idx) + 1 if idx >= 0 else 1, node))

    walk(data)
    return out


def ui_strings(path: str, text: str) -> list[tuple[int, str]]:
    ext = Path(path).suffix.lower()
    if ext in CPP_EXT:
        return cpp_strings(text)
    if ext in PY_EXT:
        return py_strings(text)
    if ext == ".json":
        return json_strings(text)
    if ext in {".ui", ".ts", ".qml", ".xml"}:
        return [(i, l) for i, l in enumerate(text.splitlines(), start=1)]
    return []


def scan_terms(path: str, strings, terms) -> list[Finding]:
    findings = []
    for lineno, s in strings:
        for term, rx in terms:
            if rx.search(s):
                findings.append(Finding("terms", path, lineno, f"reserved term '{term}' in string"))
    return findings


def check_terms(repo: Repo, scope: Scope) -> list[Finding]:
    terms = reserved_terms(repo)
    findings = []
    for rel in scope.owned_files:
        findings += scan_terms(rel, ui_strings(rel, repo.read(rel)), terms)
    for rel, lines in scope.upstream_lines.items():
        added = "\n".join(t for _, t in lines)
        strings = ui_strings(rel, added)
        # map back to file line numbers
        index = [n for n, _ in lines]
        mapped = [(index[min(l, len(index)) - 1] if index else l, s) for l, s in strings]
        findings += scan_terms(rel, mapped, terms)
    return findings


TS_SOURCE = re.compile(r"<source>(.*?)</source>", re.S)
TS_CONTEXT = re.compile(r"<name>(.*?)</name>")


def inventory_terms(repo: Repo) -> dict[str, dict[str, set[str]]]:
    """term -> {module: {source strings}} from upstream English .ts sources."""
    owned = fork_paths(repo)
    terms = reserved_terms(repo)
    report: dict[str, dict[str, set[str]]] = {}
    for rel in repo.files():
        if rel in owned or not rel.endswith(".ts"):
            continue
        if "/translations/" not in rel and "/Language/" not in rel:
            continue
        if "_" in Path(rel).stem:
            continue  # translated catalogue, not the English source
        text = repo.read(rel)
        module = Path(rel).stem
        for m in TS_SOURCE.finditer(text):
            src = re.sub(r"\s+", " ", m.group(1)).strip()
            for term, rx in terms:
                if rx.search(src):
                    report.setdefault(term, {}).setdefault(module, set()).add(src)
    return report


# --------------------------------------------------------------------------- data


DATA_GLOBS = (
    "src/Mod/*/Resources/libraries/**/*.json",
    "src/Mod/*/Resources/data/**/*.json",
)


def data_items(data) -> list[dict]:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return [d for d in data["items"] if isinstance(d, dict)]
        return [data]
    return []


def check_data(repo: Repo, scope: Scope) -> list[Finding]:
    allowed = {v.lower() for v in load_list(repo.root / "tools/fork/data_licenses.txt")}
    owned = fork_paths(repo)
    data_paths = PathSet(DATA_GLOBS)
    findings = []
    for rel in repo.files():
        if rel not in data_paths or rel not in owned:
            continue
        try:
            data = json.loads(repo.read(rel))
        except json.JSONDecodeError as e:
            findings.append(Finding("data", rel, e.lineno, f"invalid JSON: {e.msg}"))
            continue
        defaults = data if isinstance(data, dict) else {}
        for idx, item in enumerate(data_items(data)):
            ident = item.get("id", f"item {idx}")
            source = item.get("source", defaults.get("source"))
            lic = item.get("data_license", defaults.get("data_license"))
            if not source:
                findings.append(Finding("data", rel, 1, f"{ident}: missing 'source'"))
            if not lic:
                findings.append(Finding("data", rel, 1, f"{ident}: missing 'data_license'"))
            elif str(lic).lower() not in allowed:
                findings.append(Finding("data", rel, 1, f"{ident}: data_license '{lic}' not in allowlist"))
    return findings


# ------------------------------------------------------------------------ headers


def has_spdx(rel: str, text: str) -> bool:
    if rel.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False
        if isinstance(data, dict):
            return any("SPDX-License-Identifier" in str(data.get(k, "")) for k in ("_comment", "_spdx"))
        return False
    head = "\n".join(text.splitlines()[:HEADER_LINES])
    return "SPDX-License-Identifier:" in head


def check_headers(repo: Repo, scope: Scope) -> list[Finding]:
    findings = []
    for rel in repo.files():
        if rel not in fork_paths(repo):
            continue
        p = Path(rel)
        if p.name in HEADER_EXEMPT_NAMES or p.suffix.lower() not in HEADER_EXT:
            continue
        if rel.startswith("src/Mod/") and "/Resources/libraries/" in rel:
            continue  # data files: covered by the data check
        if not has_spdx(rel, repo.read(rel)):
            findings.append(Finding("headers", rel, 1, "missing SPDX-License-Identifier header"))
    base = upstream_base(repo)
    if base:
        for rel in changed_upstream_files(repo, base, fork_paths(repo)):
            if not (repo.root / rel).is_file():
                continue
            if Path(rel).suffix.lower() not in SOURCE_EXT | {".txt", ".cmake", ".in", ".ui"}:
                continue
            if "FORK:" not in repo.read(rel):
                findings.append(Finding("headers", rel, 1, "upstream file modified without a FORK: marker"))
    return findings


# --------------------------------------------------------------------------- deps

# Licenses that may be linked into an LGPL-2.1-or-later application (§1).
LINKABLE = {
    "BSL-1.0", "BSD-2-Clause", "BSD-3-Clause", "MIT", "ISC", "Zlib", "FTL", "PSF-2.0",
    "MPL-2.0", "Apache-2.0", "Artistic-2.0", "LGPL-2.0-or-later", "LGPL-2.1-only",
    "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "LGPL-2.1-only WITH OCCT-exception-1.0", "OFL-1.1", "CC0-1.0", "Unlicense",
}
# Licenses permitted only for separate executables (§1).
EXTERNAL_ONLY = {"GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0-or-later"}
LINKAGES = {"linked", "bundled-source", "external", "asset"}


def load_deps(repo: Repo) -> list[dict]:
    return json.loads((repo.root / "tools/fork/dependencies.json").read_text(encoding="utf-8"))[
        "dependencies"
    ]


def render_third_party(deps: list[dict]) -> str:
    lines = [
        "CADApp third-party components",
        "==============================",
        "",
        "CADApp is based on FreeCAD and is distributed under LGPL-2.1-or-later (see LICENSE).",
        "Binaries that link Apache-2.0 components are distributed under the terms of",
        "LGPL-3.0, as permitted by the \"or later\" clause.",
        "",
        "GPL-licensed programs listed with linkage \"external\" are separate executables",
        "invoked as child processes. They are not linked into CADApp.",
        "",
        "Version \"build\" means the version is taken from the build environment; the",
        "exact versions of a given binary are listed in Help > About > Libraries.",
        "",
        "Generated from tools/fork/dependencies.json by",
        "tools/fork/gen_third_party_licenses.py. Do not edit by hand.",
        "",
    ]
    w_name = max(len(d["name"]) for d in deps)
    w_ver = max(len(d["version"]) for d in deps)
    w_lic = max(len(d["license"]) for d in deps)
    header = f"{'Component':<{w_name}}  {'Version':<{w_ver}}  {'License (SPDX)':<{w_lic}}  Linkage"
    lines.append(header)
    lines.append("-" * len(header))
    for d in sorted(deps, key=lambda d: d["name"].lower()):
        lines.append(
            f"{d['name']:<{w_name}}  {d['version']:<{w_ver}}  {d['license']:<{w_lic}}  {d['linkage']}"
            + ("  (optional)" if d.get("optional") else "")
        )
    lines.append("")
    lines.append("Sources")
    lines.append("-------")
    for d in sorted(deps, key=lambda d: d["name"].lower()):
        entry = f"{d['name']}: {d['url']}"
        if d.get("path"):
            entry += f" (in tree: {d['path']})"
        lines.append(entry)
        if d.get("note"):
            lines.append(f"    {d['note']}")
    lines.append("")
    return "\n".join(lines)


def check_deps(repo: Repo, scope: Scope) -> list[Finding]:
    findings = []
    path = "tools/fork/dependencies.json"
    deps = load_deps(repo)
    names = set()
    for d in deps:
        name = d.get("name", "?")
        for key in ("name", "version", "license", "linkage", "origin", "url"):
            if not d.get(key):
                findings.append(Finding("deps", path, 1, f"{name}: missing '{key}'"))
        if name in names:
            findings.append(Finding("deps", path, 1, f"{name}: duplicate entry"))
        names.add(name)
        lic, link = d.get("license", ""), d.get("linkage", "")
        if link not in LINKAGES:
            findings.append(Finding("deps", path, 1, f"{name}: unknown linkage '{link}'"))
        if lic in EXTERNAL_ONLY:
            if link != "external":
                findings.append(Finding("deps", path, 1, f"{name}: {lic} allowed only as an external executable"))
        elif lic not in LINKABLE:
            findings.append(Finding("deps", path, 1, f"{name}: license '{lic}' not on the allowlist"))
        if d.get("path") and not (repo.root / d["path"]).exists():
            findings.append(Finding("deps", path, 1, f"{name}: path '{d['path']}' does not exist"))
    tpl = repo.root / "THIRD_PARTY_LICENSES"
    if not tpl.exists() or tpl.read_text(encoding="utf-8") != render_third_party(deps):
        findings.append(
            Finding("deps", "THIRD_PARTY_LICENSES", 1, "out of date; run tools/fork/gen_third_party_licenses.py")
        )
    return findings


# ---------------------------------------------------------------------------- cli


CHECKS = {
    "network": check_network,
    "terms": check_terms,
    "data": check_data,
    "headers": check_headers,
    "deps": check_deps,
}


def run(repo: Repo, names: list[str]) -> int:
    scope = build_scope(repo)
    warn_no_base(scope)
    total = 0
    for name in names:
        findings = CHECKS[name](repo, scope)
        for f in findings:
            print(f)
        status = "ok" if not findings else f"{len(findings)} finding(s)"
        print(f"[{name}] {status}", file=sys.stderr)
        total += len(findings)
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("check", choices=[*CHECKS, "all", "inventory"])
    parser.add_argument("--repo", type=Path, help="repository root (default: this checkout)")
    parser.add_argument("--json", action="store_true", help="inventory: print JSON")
    args = parser.parse_args(argv)
    repo = Repo(args.repo.resolve()) if args.repo else default_repo()
    if args.check == "inventory":
        report = inventory_terms(repo)
        if args.json:
            print(json.dumps({t: {m: sorted(s) for m, s in mods.items()} for t, mods in report.items()}, indent=2))
        else:
            for term in sorted(report):
                for module in sorted(report[term]):
                    print(f"{term}\t{module}\t{len(report[term][module])}")
        return 0
    names = list(CHECKS) if args.check == "all" else [args.check]
    return run(repo, names)


if __name__ == "__main__":
    sys.exit(main())
