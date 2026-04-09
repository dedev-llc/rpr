# rpr — Stealth PR Reviewer

AI-powered PR reviews that look like you wrote them. No GitHub Apps, no bots, no traces.

## What It Does

1. Fetches the PR diff from GitHub
2. Sends it to Claude with a prompt engineered to sound like a senior engineer (not AI)
3. Posts the review under **your GitHub account**  inline comments on specific lines

Nobody can tell the difference.

## Install

| Channel | Command |
|---|---|
| **pipx** (recommended) | `pipx install rpr` |
| **pip**  | `pip install --user rpr` |
| **Homebrew** | `brew install dedev-llc/rpr/rpr` |
| **npm**  | `npm install -g @dedev-llc/rpr` |
| **npx**  | `npx @dedev-llc/rpr <pr-number>` |
| **curl** | `curl -fsSL https://raw.githubusercontent.com/dedev-llc/rpr/main/install.sh \| bash` |

All channels install the same `rpr` command. You'll also need:

- **GitHub CLI (`gh`)** — [install](https://cli.github.com/), then `gh auth login`
- **Anthropic API key** — `export ANTHROPIC_API_KEY=sk-ant-...` ([get one](https://console.anthropic.com/))
- **Python 3.9+** (already required by all channels except npm/npx, which need it on PATH at runtime)

## Usage

```bash
# In any git repo:
rpr 42                                   # Review PR #42
rpr 42 --dry-run                         # Preview in terminal first
rpr 42 --approve                         # Review + approve
rpr 42 --request-changes                 # Review + request changes
rpr 42 --comment-only                    # Post as single comment (no inline)
rpr 42 --repo owner/repo                 # Specify repo explicitly
rpr 42 --model claude-sonnet-4-6         # Override model
rpr 42 -v                                # Verbose mode (debug)
```

### Recommended Workflow

1. **Always dry-run first** until you trust the output:
   ```bash
   rpr 42 --dry-run
   ```

2. If it looks right, post it:
   ```bash
   rpr 42
   ```

3. Optionally tweak a word or two in the posted review for your personal touch.

## Configuration

`rpr` ships with sensible defaults. To override them, drop a config file at one of these paths (first match wins):

1. `./rpr.config.json` — project-local override (per-repo)
2. `~/.config/rpr/config.json` — user-wide

Example (see `examples/config.json`):

```json
{
  "model": "claude-opus-4-6",
  "max_tokens": 16000,
  "max_diff_chars": 120000,
  "skip_patterns": [
    "*.lock",
    "*.g.dart",
    "*.freezed.dart"
  ]
}
```

| Key | Meaning |
|---|---|
| `model` | Claude model to use |
| `max_tokens` | Max response length |
| `max_diff_chars` | Truncate diffs larger than this |
| `skip_patterns` | Glob patterns for files to ignore (generated code, locks, etc.) |

### Custom review guidelines

Inject your team's coding standards by dropping a `review-guidelines.md` at:

1. `./review-guidelines.md` — project-local (per-repo)
2. `~/.config/rpr/review-guidelines.md` — user-wide

The contents get appended to the system prompt and the AI enforces them as if they were your personal standards. See `examples/review-guidelines.md` for a starter template.

## How It Stays Invisible

| Concern | Solution |
|---|---|
| GitHub Actions history | None — runs locally on your machine |
| Workflow files in repo | None — no `.github/workflows` needed |
| Bot label on comments | None — uses your PAT via `gh` CLI |
| AI-sounding language | Prompt is engineered to sound human |
| Review pattern detection | Varies tone, uses informal language |

## Cost

Each review costs roughly $0.01–$0.08 depending on diff size and model:

- Small PR (< 200 lines): ~$0.01
- Medium PR (200–1000 lines): ~$0.03
- Large PR (1000+ lines): ~$0.05–0.08

## Tips

- **Edit after posting**: Tweak a word or two in your posted review for authenticity.
- **Use `--dry-run` liberally**: Especially on important PRs.
- **Customize guidelines**: The more specific your `review-guidelines.md`, the better the reviews match your real style.
- **Skip generated files**: Add patterns for code generators your team uses (Freezed, json_serializable, etc.) to avoid noise.

## Development

```bash
git clone https://github.com/dedev-llc/rpr
cd rpr
python -m venv .venv && source .venv/bin/activate
pip install -e .         # editable install — `rpr` command works from anywhere
rpr --help
```

Run as a module: `python -m rpr 42 --dry-run`

> **macOS gotcha**: do **not** clone the repo into `~/Desktop` (or `~/Documents`). macOS sets the `UF_HIDDEN` file flag on everything inside those App Sandbox directories, which makes Python 3.13's `site.py` skip the editable install's `.pth` file (it treats hidden-flagged files as hidden, regardless of name). The published wheel from PyPI is unaffected — this only bites editable dev installs in sandboxed dirs. Symptom: `ModuleNotFoundError: No module named 'rpr'` after `pip install -e .`. Fix: clone to `~/code/rpr` or somewhere outside the sandbox.

## Publishing (maintainer notes)

The PyPI package is the source of truth. Other channels wrap it.

### PyPI

```bash
pip install build twine
python -m build                              # produces dist/rpr-X.Y.Z.tar.gz + .whl
twine upload dist/*                          # requires PyPI account + token
```

### Homebrew formula

After publishing to PyPI, update `Formula/rpr.rb`:

```bash
SHA=$(curl -sL https://files.pythonhosted.org/packages/source/r/rpr/rpr-0.1.0.tar.gz | shasum -a 256 | cut -d' ' -f1)
# Edit Formula/rpr.rb: replace the placeholder sha256 with $SHA, bump version in url
git commit -am "brew: bump rpr to 0.1.0" && git push
```

Users install via: `brew install dedev-llc/rpr/rpr`

### npm

```bash
cd npm
npm version 0.1.0 --no-git-tag-version       # match pyproject.toml version
npm pack --dry-run                           # sanity check: should list bin/ + lib/
npm publish                                  # requires npm login
```

The `prepack` hook copies `src/rpr/*.py` into `npm/lib/` automatically.

### Release checklist

1. Bump version in `pyproject.toml`, `src/rpr/__init__.py`, `npm/package.json`, `Formula/rpr.rb` (`url`)
2. Tag: `git tag v0.1.0 && git push --tags`
3. Publish to PyPI (above)
4. Update Homebrew formula sha256 (above)
5. Publish to npm (above)
