 f# Contributing to rpr

Thanks for your interest in improving `rpr`. This is a small project — the bar for contributions is "make it better without making it weirder." Bug reports, fixes, and modest features are all welcome.

## Quick links

- **Bugs**: open an issue using the [Bug report](https://github.com/dedev-llc/rpr/issues/new?template=bug_report.yml) template
- **Features**: open an issue using the [Feature request](https://github.com/dedev-llc/rpr/issues/new?template=feature_request.yml) template — please discuss before writing a large PR
- **Security issues**: see [SECURITY.md](SECURITY.md), do **not** open a public issue
- **Code of Conduct**: see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

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
6. **Update [`CHANGELOG.md`](CHANGELOG.md)** under the `[Unreleased]` section with a one-line summary of your change.

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
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No new runtime dependencies added (or change discussed in an issue first)
- [ ] Commit messages are descriptive

## Releasing (maintainers only)

See the **Publishing** section of [README.md](README.md#publishing-maintainer-notes) for the manual PyPI / npm / Homebrew release steps. The flow is roughly:

1. Bump the version in `pyproject.toml`, `src/rpr/__init__.py`, `npm/package.json`, and `Formula/rpr.rb`
2. Move `[Unreleased]` entries in `CHANGELOG.md` to a new `[X.Y.Z] - YYYY-MM-DD` section
3. Tag and publish in this order: PyPI → Homebrew (sha256 update) → npm

## Questions

Open an issue with the `question` label, or start a discussion if discussions are enabled on the repo.
