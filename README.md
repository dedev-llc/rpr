# rpr — Stealth PR Reviewer

AI-powered PR reviews that look like you wrote them. No GitHub Apps, no bots, no traces.

## What It Does

1. Fetches the PR diff from GitHub
2. Sends it to Claude with a prompt engineered to sound like a senior engineer (not AI)
3. Posts the review under **your GitHub account** — inline comments on specific lines

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

# Review depth:
rpr 42 --depth quick                     # Blockers & security only (fast)
rpr 42 --depth thorough                  # Deep: architecture, edge cases, scale
rpr 42                                   # Default depth (balanced)

# Self-update:
rpr update                               # Update to latest version
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

### Review Depth

Control how deep the review goes with `--depth` / `-d`:

| Depth | Flag | What gets flagged |
|---|---|---|
| **quick** | `-d quick` | Production bugs, security vulnerabilities, data loss risks, major architectural violations. Skips nits and style. |
| **default** | *(omit flag)* | Bugs, security, performance, error handling, concurrency, resource leaks. Skips style preferences and obvious suggestions. |
| **thorough** | `-d thorough` | Everything in default, plus architecture fit, edge cases, naming clarity, API design, testability, and performance at scale. |

```bash
rpr 42 -d quick      # Quick scan before a fast merge
rpr 42               # Standard review (default)
rpr 42 -d thorough   # Critical code path — go deep
```

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

Releases are fully automated by [`.github/workflows/release.yml`](.github/workflows/release.yml). Merging a version bump to `main` publishes to PyPI, npm, and the Homebrew tap in one shot, then tags `v<version>` and cuts a GitHub release. Merges that don't change the version are no-ops.

### Cutting a release

```bash
scripts/bump.sh 0.1.2          # updates pyproject.toml, npm/package.json, src/rpr/__init__.py
git checkout -b release/v0.1.2
git commit -am "Release v0.1.2"
gh pr create --fill            # review, merge — workflow does the rest
```

That's it. The workflow:

1. Reads the new version, fails fast if the three files disagree, skips if `v0.1.2` is already tagged
2. Builds + uploads the sdist/wheel to PyPI via **Trusted Publishing** (OIDC, no token)
3. Publishes `@dedev-llc/rpr` to npm (the `prepack` hook bundles `src/rpr/*.py` into `npm/lib/`)
4. Resolves the real PyPI sdist URL+sha256, rewrites `Formula/rpr.rb` in the [`dedev-llc/homebrew-rpr`](https://github.com/dedev-llc/homebrew-rpr) tap, and pushes
5. Tags `v0.1.2` on this repo and creates a GitHub release with auto-generated notes

### Required secrets and one-time setup

- **`NPM_TOKEN`** — Automation token for `@dedev-llc` org publish rights
- **`HOMEBREW_TAP_TOKEN`** — Fine-grained PAT, `Contents: read/write` on `dedev-llc/homebrew-rpr`
- **PyPI Trusted Publisher** — Configured at https://pypi.org/manage/account/publishing/ with workflow `release.yml` and environment `release`
- **`release` GitHub Environment** — Repo Settings → Environments → New environment → name `release`
- **`dedev-llc/homebrew-rpr` repo** — Must exist with a seed `Formula/rpr.rb` committed before the first run

### Manual fallback (rarely needed)

If the workflow can't run for some reason, you can publish by hand. The `pypi` step is `python -m build && twine upload dist/*` (with a PyPI API token), `npm publish --access public` runs from the `npm/` dir, and the Homebrew formula update is whatever the workflow's `homebrew` job does — see [`.github/workflows/release.yml`](.github/workflows/release.yml) as the canonical reference.
