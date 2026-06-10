#!/usr/bin/env bash
# Definition of done. ALL steps must pass before claiming a feature complete.
# Exit 0 = verified done. Non-zero = not done.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== verify: definition of done =="

# TEMPLATE: delete this guard during bootstrap.
if [[ -f TEMPLATE_SETUP.md ]]; then
  echo "TEMPLATE_SETUP.md exists: verify pipeline not configured yet."
  echo "Fill the TODO(setup) blocks below as part of template setup."
  exit 1
fi

# TODO(setup): replace with real commands, remove the exit 1 fallback.
# Keep order: cheap/fast checks first.
#
#   echo "-- lint --";      npm run lint
#   echo "-- typecheck --"; npm run typecheck
#   echo "-- test --";      npm test
#   echo "-- build --";     npm run build

echo "verify.sh not configured (TODO(setup) blocks unfilled)."
exit 1

# When configured, end with:
# echo "== verify OK: all checks green =="
