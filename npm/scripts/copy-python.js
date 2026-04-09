#!/usr/bin/env node
// Prepack hook: copies the canonical Python source from ../src/rpr into ./lib
// so the published npm tarball ships the .py files alongside the Node shim.
//
// The dev repo never commits ./lib (see .gitignore). This script runs
// automatically on `npm pack` and `npm publish`.

"use strict";

const fs = require("fs");
const path = require("path");

const here = __dirname;
const npmRoot = path.resolve(here, "..");
const repoRoot = path.resolve(npmRoot, "..");
const src = path.join(repoRoot, "src", "rpr");
const dest = path.join(npmRoot, "lib");

if (!fs.existsSync(src)) {
  console.error(
    "copy-python: source not found at " + src + ".\n" +
      "             This script must run from the rpr monorepo (npm/ subdir)."
  );
  process.exit(1);
}

// Wipe and recreate lib/ to avoid stale files.
fs.rmSync(dest, { recursive: true, force: true });
fs.mkdirSync(dest, { recursive: true });

// Copy every .py file from src/rpr (non-recursive — the package is flat).
const entries = fs.readdirSync(src, { withFileTypes: true });
let copied = 0;
for (const entry of entries) {
  if (!entry.isFile() || !entry.name.endsWith(".py")) continue;
  fs.copyFileSync(path.join(src, entry.name), path.join(dest, entry.name));
  copied += 1;
}

if (copied === 0) {
  console.error("copy-python: no .py files found in " + src);
  process.exit(1);
}

console.log("copy-python: bundled " + copied + " Python file(s) into " + path.relative(repoRoot, dest));
