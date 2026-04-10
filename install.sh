#!/usr/bin/env bash
# rpr installer — stealth PR reviewer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/dedev-llc/rpr/main/install.sh | bash
#
# Tries pipx → pip --user → raw script download (in that order). Idempotent:
# safe to re-run.

set -euo pipefail

REPO="dedev-llc/rpr"
PKG="rpr"
RAW_SCRIPT_URL="https://raw.githubusercontent.com/${REPO}/main/src/rpr/cli.py"
LOCAL_BIN="${HOME}/.local/bin"

# ----- output helpers -------------------------------------------------------
if [ -t 1 ]; then
  BOLD=$(printf '\033[1m')
  DIM=$(printf '\033[2m')
  RED=$(printf '\033[31m')
  GREEN=$(printf '\033[32m')
  YELLOW=$(printf '\033[33m')
  RESET=$(printf '\033[0m')
else
  BOLD="" DIM="" RED="" GREEN="" YELLOW="" RESET=""
fi

info()  { printf "%s\n" "${DIM}==>${RESET} $*"; }
ok()    { printf "%s\n" "${GREEN}✓${RESET} $*"; }
warn()  { printf "%s\n" "${YELLOW}!${RESET} $*"; }
fail()  { printf "%s\n" "${RED}✗${RESET} $*" >&2; exit 1; }

have()  { command -v "$1" >/dev/null 2>&1; }

banner() {
  printf "%s\n" "${BOLD}rpr installer${RESET}"
  printf "%s\n" "${DIM}stealth PR reviewer — looks like you wrote every word${RESET}"
  printf "\n"
}

# ----- prerequisite checks --------------------------------------------------

check_python() {
  if ! have python3; then
    fail "python3 not found. Install Python 3.9+ first:
    macOS:  brew install python
    Debian: sudo apt install python3 python3-pip
    Other:  https://www.python.org/downloads/"
  fi

  local pyver
  pyver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  local major minor
  major=${pyver%.*}
  minor=${pyver#*.}
  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 9 ]; }; then
    fail "python3 is ${pyver}, need >= 3.9"
  fi
  ok "python3 ${pyver}"
}

check_gh() {
  if have gh; then
    ok "gh CLI found"
  else
    warn "gh CLI not found — rpr needs it at runtime."
    warn "  macOS:  brew install gh"
    warn "  Debian: sudo apt install gh"
    warn "  Other:  https://cli.github.com/"
  fi
}

# ----- install strategies ---------------------------------------------------

try_pipx() {
  if ! have pipx; then
    return 1
  fi
  info "Installing via pipx..."
  if pipx install --force "${PKG}" >/dev/null 2>&1; then
    ok "Installed ${PKG} via pipx"
    return 0
  fi
  warn "pipx install failed, falling back..."
  return 1
}

try_pip_user() {
  if ! have pip3 && ! have pip; then
    return 1
  fi
  local pip_cmd
  if have pip3; then pip_cmd=pip3; else pip_cmd=pip; fi
  info "Installing via ${pip_cmd} --user..."
  if "${pip_cmd}" install --user --upgrade "${PKG}" >/dev/null 2>&1; then
    ok "Installed ${PKG} via ${pip_cmd} --user"
    return 0
  fi
  warn "${pip_cmd} --user install failed, falling back..."
  return 1
}

try_raw_download() {
  info "Falling back to raw script download → ${LOCAL_BIN}/rpr"
  mkdir -p "${LOCAL_BIN}"
  if have curl; then
    curl -fsSL "${RAW_SCRIPT_URL}" -o "${LOCAL_BIN}/rpr" || fail "download failed: ${RAW_SCRIPT_URL}"
  elif have wget; then
    wget -q "${RAW_SCRIPT_URL}" -O "${LOCAL_BIN}/rpr" || fail "download failed: ${RAW_SCRIPT_URL}"
  else
    fail "neither curl nor wget available"
  fi
  chmod +x "${LOCAL_BIN}/rpr"
  ok "Downloaded ${LOCAL_BIN}/rpr"
}

# ----- post-install ---------------------------------------------------------

verify_install() {
  if have rpr; then
    ok "$(rpr --help 2>&1 | head -n1)"
    return 0
  fi
  return 1
}

print_path_hint() {
  case ":${PATH}:" in
    *":${LOCAL_BIN}:"*) ;;
    *)
      warn "${LOCAL_BIN} is not on your PATH."
      warn "  Add to your shell profile (~/.zshrc or ~/.bashrc):"
      warn "    export PATH=\"${LOCAL_BIN}:\$PATH\""
      ;;
  esac
}

print_next_steps() {
  printf "\n"
  printf "%s\n" "${BOLD}Next steps:${RESET}"
  printf "  1. Set your Anthropic API key:  %sexport ANTHROPIC_API_KEY=sk-ant-...%s\n" "$DIM" "$RESET"
  printf "  2. Authenticate gh:             %sgh auth login%s\n" "$DIM" "$RESET"
  printf "  3. Try a dry-run review:        %srpr <pr-number> --dry-run%s\n" "$DIM" "$RESET"
  printf "\n"
  printf "Docs: https://github.com/%s\n" "${REPO}"
}

# ----- main -----------------------------------------------------------------

main() {
  banner
  check_python
  check_gh
  printf "\n"

  if try_pipx; then :
  elif try_pip_user; then :
  else try_raw_download
  fi

  printf "\n"

  if ! verify_install; then
    print_path_hint
  fi
  print_next_steps
}

main "$@"
