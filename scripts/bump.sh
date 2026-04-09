#!/usr/bin/env bash
# bump.sh — bump rpr version in pyproject.toml and npm/package.json in lockstep.
#
# Usage:
#   scripts/bump.sh 0.2.0
#
# Does NOT commit, tag, or push — just edits the two files so you can review
# the diff and open a PR. The release workflow runs on merge to main and
# detects the new version automatically.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <version>" >&2
  exit 1
fi

new="$1"

# PEP 440 / semver-ish: MAJOR.MINOR.PATCH with optional pre/post/dev suffix.
if ! [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9.+-]*)?$ ]]; then
  echo "error: '$new' is not a valid version (expected MAJOR.MINOR.PATCH[suffix])" >&2
  exit 1
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

current=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
echo "Current version: $current"
echo "New version:     $new"

if [ "$current" = "$new" ]; then
  echo "Already at $new — nothing to do."
  exit 0
fi

# pyproject.toml — surgical replace of the project.version line.
NEW="$new" python3 - <<'PY'
import os, pathlib, re
p = pathlib.Path("pyproject.toml")
s = p.read_text()
s, n = re.subn(r'^version\s*=\s*"[^"]+"',
               f'version = "{os.environ["NEW"]}"',
               s, count=1, flags=re.M)
if n != 1:
    raise SystemExit("error: could not find 'version = ...' line in pyproject.toml")
p.write_text(s)
PY

# src/rpr/__init__.py — surgical replace of the __version__ line.
NEW="$new" python3 - <<'PY'
import os, pathlib, re
p = pathlib.Path("src/rpr/__init__.py")
s = p.read_text()
s, n = re.subn(r'^__version__\s*=\s*"[^"]+"',
               f'__version__ = "{os.environ["NEW"]}"',
               s, count=1, flags=re.M)
if n != 1:
    raise SystemExit("error: could not find '__version__ = ...' line in src/rpr/__init__.py")
p.write_text(s)
PY

# npm/package.json — preserve 2-space indent and trailing newline.
NEW="$new" node -e '
const fs = require("fs");
const p  = "npm/package.json";
const j  = JSON.parse(fs.readFileSync(p, "utf8"));
j.version = process.env.NEW;
fs.writeFileSync(p, JSON.stringify(j, null, 2) + "\n");
'

echo
echo "Updated:"
echo "  pyproject.toml"
echo "  src/rpr/__init__.py"
echo "  npm/package.json"
echo
echo "Next steps:"
echo "  git checkout -b release/v$new"
echo "  git commit -am \"Release v$new\""
echo "  gh pr create --fill"
