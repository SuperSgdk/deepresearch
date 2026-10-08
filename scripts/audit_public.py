"""Scan Git-visible files for private artifacts and common secret patterns.

This is a release check, not a substitute for reviewing the commit contents.
Only filenames and matching rule names are printed; secret values stay hidden.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "provider_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential_url": re.compile(r"://[^\s/:]+:(?!CHANGE_ME@)[^\s/@]+@"),
    "personal_absolute_path": re.compile(r"(?:[A-Z]:[\\/]Users[\\/]|/Users/|/home/)[A-Za-z0-9_.-]+", re.I),
}


PRIVATE_FIELDS = re.compile(r"(?:api_?key|token|secret|password|passwd|api_base|base_url|endpoint|email|phone)$", re.I)


def placeholder(value):
    return not value or str(value).upper().startswith(("CHANGE_ME", "YOUR_", "REPLACE_", "EXAMPLE_"))


def inspect_content(name, data, private_values=()):
    path = Path(name)
    issues = set()
    if any(p in {".venv", "node_modules", "logs", "output", ".setup", ".local"} for p in path.parts) or path.suffix in {".db", ".sqlite", ".log", ".pyc"} or (path.name.startswith(".env") and path.name != ".env.example"):
        issues.add("private_artifact")
    if any(value in data for value in private_values):
        issues.add("matches_private_configuration")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return issues
    issues.update(rule for rule, pattern in RULES.items() if pattern.search(content))
    if path.name == ".env.example":
        values = dict(re.findall(r"^([A-Z_][A-Z_0-9]*)=(.*)$", content, re.M))
    elif path.name == "config.json":
        try:
            values = json.loads(content)
        except ValueError:
            issues.add("invalid_configuration")
            values = {}
    else:
        values = {}
    if isinstance(values, dict):
        for key, value in values.items():
            if PRIVATE_FIELDS.search(key) and not placeholder(str(value or "").strip().strip("\"'")):
                issues.add("private_configuration_value")
    return issues


def git_output(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also scan every commit reachable from local refs")
    parser.add_argument("--private-env", action="append", type=Path, default=[], help="Compare local private values without printing them")
    args = parser.parse_args()
    private_values = set()
    for path in args.private_env:
        if not path.is_file():
            parser.error("A supplied private configuration file is missing")
        for key, value in dotenv_values(path).items():
            if value and re.search(r"KEY|TOKEN|SECRET|PASSWORD|DSN|BASE_URL|ENDPOINT", key, re.I) and not placeholder(value):
                if len(value) >= 8:
                    private_values.add(value.encode())
                try:
                    password = urlparse(value).password
                    if password and len(password) >= 8 and not placeholder(password):
                        private_values.add(password.encode())
                except ValueError:
                    pass
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            cwd=ROOT, check=True, capture_output=True)
    failures = set()
    files = sorted(set(result.stdout.decode().split("\0")) - {""})
    for name in files:
        path = ROOT / name
        if not path.is_file():
            continue
        failures.update((name, rule) for rule in inspect_content(name, path.read_bytes(), private_values))
    snapshots = set()
    if args.history:
        for commit in git_output("rev-list", "--all").decode().splitlines():
            for entry in git_output("ls-tree", "-r", "-z", commit).split(b"\0"):
                if not entry:
                    continue
                metadata, raw_name = entry.split(b"\t", 1)
                _, kind, oid = metadata.decode().split()
                name = raw_name.decode("utf-8")
                if kind != "blob" or (name, oid) in snapshots:
                    continue
                snapshots.add((name, oid))
                failures.update((name, rule) for rule in inspect_content(name, git_output("cat-file", "blob", oid), private_values))
    for name, rule in sorted(failures):
        print(f"FAIL {name}: {rule}")
    print(f"Scanned {len(files)} Git-visible files; findings: {len(failures)}")
    if args.history:
        print(f"Historical file snapshots scanned: {len(snapshots)}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
