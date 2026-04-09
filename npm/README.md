# rpr

Stealth PR reviewer — looks like you wrote every word.

This is the npm distribution of `rpr`. It bundles the Python source and runs it via your local `python3`. You'll need:

- **Python 3.9+** on your `PATH`
- **GitHub CLI (`gh`)**, authenticated
- **`ANTHROPIC_API_KEY`** environment variable

## Install

```bash
npm install -g @dedev-llc/rpr
# or
npx @dedev-llc/rpr <pr-number>
```

After install, the CLI is just `rpr` — the scope only affects the install command, not the binary name.

## Usage

```bash
rpr 42                         # Review PR #42 in current repo
rpr 42 --dry-run               # Print review, don't post
rpr 42 --approve               # Review + approve
rpr 42 --request-changes       # Review + request changes
rpr 42 --repo owner/repo       # Specify a different repo
```

See the [main repo](https://github.com/dedev-llc/rpr) for full docs and configuration.

## Why a Node wrapper around Python?

`rpr` is written in Python (stdlib only). The npm package is a thin Node shim that finds your `python3` and execs the bundled CLI. If you're already a Python user, install via `pipx install rpr` instead — it's more idiomatic.

The npm package is published under the `@dedev-llc` scope because the unscoped `rpr` name was already taken on the npm registry by an unrelated package.
