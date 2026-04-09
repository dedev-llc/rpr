#!/usr/bin/env node
// rpr — stealth PR reviewer (Node shim)
//
// This is a thin wrapper around the bundled Python CLI. The npm package
// ships the Python source under ./lib/ (populated by scripts/copy-python.js
// at prepack time). This shim finds a Python 3 interpreter on PATH and
// execs the package's __main__.py with the user's arguments.

"use strict";

const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const libDir = path.join(__dirname, "..", "lib");
const entryPoint = path.join(libDir, "cli.py");

if (!fs.existsSync(entryPoint)) {
  console.error(
    "rpr: bundled Python source missing at " + entryPoint + ".\n" +
      "     Reinstall the npm package, or install via pipx instead:\n" +
      "       pipx install rpr"
  );
  process.exit(1);
}

// On Windows, prefer the py launcher; elsewhere prefer python3.
const candidates =
  process.platform === "win32"
    ? ["py", "python3", "python"]
    : ["python3", "python"];

let python = null;
for (const candidate of candidates) {
  const probe = spawnSync(candidate, ["--version"], { stdio: "ignore" });
  if (probe.status === 0) {
    python = candidate;
    break;
  }
}

if (!python) {
  console.error(
    "rpr: Python 3 not found on PATH.\n" +
      "     Install Python 3.9+ and retry, or use pipx:\n" +
      "       pipx install rpr"
  );
  process.exit(1);
}

// cli.py is self-contained (stdlib only, no relative imports) and has its
// own `if __name__ == "__main__": main()` guard, so we can exec it directly.
const cliPath = path.join(libDir, "cli.py");
const result = spawnSync(python, [cliPath, ...process.argv.slice(2)], {
  stdio: "inherit",
});

process.exit(result.status === null ? 1 : result.status);
