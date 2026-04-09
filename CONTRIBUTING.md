# Contributing to rpr

Thanks for your interest in improving `rpr`. This is a small project — the bar for contributions is "make it better without making it weirder." Bug reports, fixes, and modest features are all welcome.

## Quick links

- **Bugs and features**: [open an issue](https://github.com/dedev-llc/rpr/issues/new) — please discuss before writing a large PR
- **Security issues**: email the maintainers privately rather than opening a public issue

## Project layout

```
rpr/
├── src/rpr/              ← canonical Python source (cli.py is the script)
├── examples/             ← config + guidelines templates
├── npm/                  ← npm wrapper (Node shim that execs the Python)
├── Formula/rpr.rb        ← Homebrew formula
├── install.sh            ← curl-pipe installer
├── pyproject.toml        ← Python package metadata
└── README.md
```

The Python package on PyPI is the source of truth. The npm package, Homebrew formula, and curl installer all wrap it.

## Development setup

You need **Python 3.9+**, `git`, and (for full testing) `node` + `npm` and the `gh` CLI.

```bash
git clone https://github.com/dedev-llc/rpr
cd rpr
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
rpr --help                          # should print the argparse help
```

> **macOS users**: do not clone into `~/Desktop` or `~/Documents`. Files inside macOS App Sandbox directories get the `UF_HIDDEN` flag, which makes Python 3.13's `site.py` skip the editable install's `.pth` file. Symptom: `ModuleNotFoundError: No module named 'rpr'` after a successful `pip install -e .`. Clone to `~/code/rpr` or similar.

To run a real review against a PR you've already opened:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
rpr <pr-number> --dry-run -v
```

## Making changes

1. **Fork & branch.** `git checkout -b fix/short-description`
2. **Keep changes small and focused.** One logical change per PR. If you're touching multiple things, split them.
3. **Match the existing style.** No new dependencies (the script is stdlib-only on purpose). No reformatters. No drive-by refactors.
4. **Test your change end-to-end.** Run `rpr --dry-run` against a real PR to make sure the output still looks right.
5. **Update docs.** If you change CLI flags, config keys, or install steps, update the README and the relevant section here.

## Things to avoid

- **Adding runtime dependencies.** The Python package is intentionally stdlib-only. If you really need a dep, open an issue first.
- **Reformatting unrelated code.** Don't run `black` or `ruff format` over files you didn't otherwise touch.
- **Adding heavy abstractions** for one-off logic. The script is small on purpose.
- **Mass-renaming things.** If you want to rename `rpr` to `rapper`, that's a separate conversation.

## Pull request checklist

- [ ] Branch is up to date with `main`
- [ ] Change is focused (one logical thing per PR)
- [ ] `rpr --dry-run` against a real PR still works
- [ ] README / examples updated if user-facing behavior changed
- [ ] No new runtime dependencies added (or change discussed in an issue first)
- [ ] Commit messages are descriptive

## Releasing (maintainers only)

Releases are automated by [`.github/workflows/release.yml`](.github/workflows/release.yml). The full flow:

```bash
scripts/bump.sh 0.1.2          # bumps pyproject.toml, npm/package.json, src/rpr/__init__.py
git checkout -b release/v0.1.2
git commit -am "Release v0.1.2"
gh pr create --fill            # review, merge — workflow publishes to PyPI, npm, and Homebrew
```

The workflow's preflight check fails fast if the three version files drift, so always use `scripts/bump.sh` rather than editing them by hand. See the **Publishing** section of [README.md](README.md#publishing-maintainer-notes) for the secrets and one-time setup the workflow depends on.

## Branch protection (maintainers only)

The `main` branch is protected by a ruleset defined in [`scripts/setup-branch-protection.sh`](scripts/setup-branch-protection.sh). The ruleset enforces:

- No deletion of `main`, no force-pushes
- Linear history (squash or rebase merges only)
- All changes go through a pull request
- All CI checks in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) must pass before merge
- Conversations resolved before merge
- Org admins (i.e. maintainers) may bypass in an emergency

GitHub gates rulesets behind a paid plan for **private** repos. While the repo is private, the script can't apply the ruleset (CI still runs on PRs, but the rules aren't enforced). After flipping the repo to public:

```bash
scripts/setup-branch-protection.sh
```

The script is idempotent — re-run it any time you add or remove CI jobs (just update the `REQUIRED_CHECKS` array first).

## Questions

Open an issue with the `question` label, or start a discussion if discussions are enabled on the repo.
