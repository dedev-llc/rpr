#!/usr/bin/env bash
# setup-branch-protection.sh — apply the main-branch ruleset to dedev-llc/rpr.
#
# Idempotent: re-running updates the existing ruleset rather than duplicating.
#
# WHEN TO RUN:
#   - After flipping the repo from private → public (rulesets are paywalled
#     on private repos with the free GitHub plan).
#   - After adding/removing CI checks in .github/workflows/ci.yml — update
#     the REQUIRED_CHECKS array below to match the new job names.
#
# REQUIREMENTS:
#   - gh CLI authenticated as a dedev-llc org admin
#   - The CI workflow (.github/workflows/ci.yml) must already exist on main,
#     otherwise the required status checks will block all PRs forever (no run
#     can ever produce them).
#
# WHAT THE RULESET ENFORCES:
#   - No deletion of main
#   - No force pushes (non-fast-forward) to main
#   - Linear history (no merge commits inside PRs — squash/rebase only)
#   - All changes go through a pull request
#   - PR conversations must be resolved before merge
#   - Stale review approvals are dismissed when new commits are pushed
#   - All required CI checks must pass before merge
#   - Org admins can bypass in an emergency (configurable below)

set -euo pipefail

REPO="dedev-llc/rpr"
RULESET_NAME="main-protection"

# Required CI status check job names — must match the `name:` (or job key when
# no name is set) of the jobs in .github/workflows/ci.yml. For matrix jobs,
# include each variant explicitly.
REQUIRED_CHECKS=(
  "python (3.9)"
  "python (3.10)"
  "python (3.11)"
  "python (3.12)"
  "version-sync"
  "json-lint"
  "shellcheck"
  "npm-pack"
)

# Build the JSON array of required status checks.
contexts_json=$(printf '%s\n' "${REQUIRED_CHECKS[@]}" \
  | python3 -c '
import json, sys
checks = [{"context": line.strip()} for line in sys.stdin if line.strip()]
print(json.dumps(checks))
')

# Build the full ruleset payload. Heredoc + envsubst-style substitution would
# be cleaner but we want zero dependencies — using python for JSON assembly.
ruleset_json=$(CONTEXTS="$contexts_json" python3 - <<'PY'
import json, os
payload = {
    "name": "main-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {
        "ref_name": {
            "include": ["~DEFAULT_BRANCH"],
            "exclude": [],
        }
    },
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "required_linear_history"},
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["squash", "rebase"],
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": json.loads(os.environ["CONTEXTS"]),
            },
        },
    ],
    "bypass_actors": [
        # OrganizationAdmin = anyone with org admin role on dedev-llc.
        # bypass_mode "always" means they can bypass without going through
        # the normal flow (e.g. emergency direct push). Change to "pull_request"
        # to require admins to still go through a PR but skip the checks.
        {
            "actor_id": 1,
            "actor_type": "OrganizationAdmin",
            "bypass_mode": "always",
        }
    ],
}
print(json.dumps(payload, indent=2))
PY
)

echo "Target repo:   $REPO"
echo "Ruleset name:  $RULESET_NAME"
echo "Required checks:"
printf '  - %s\n' "${REQUIRED_CHECKS[@]}"
echo

# Look for an existing ruleset with the same name.
existing_id=$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$RULESET_NAME\") | .id" 2>/dev/null || true)

if [ -n "$existing_id" ]; then
  echo "Updating existing ruleset (id=$existing_id)..."
  printf '%s' "$ruleset_json" | gh api -X PUT "repos/$REPO/rulesets/$existing_id" --input - > /dev/null
  echo "✓ Ruleset updated"
else
  echo "Creating new ruleset..."
  printf '%s' "$ruleset_json" | gh api -X POST "repos/$REPO/rulesets" --input - > /dev/null
  echo "✓ Ruleset created"
fi

echo
echo "View at: https://github.com/$REPO/rules"
