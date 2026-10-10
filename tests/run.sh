#!/usr/bin/env bash
# Runs the tests.
#   tests/run.sh             everything
#   tests/run.sh static      parsing, builds, configs, nothing private, README coverage
#   tests/run.sh unit        the installers' helpers, and the change record with --restore
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
what="${1:-all}"; shift || true
status=0
if [[ $what == all || $what == static ]]; then bash "$HERE/static.sh" || status=1; fi
if [[ $what == all || $what == unit ]];   then bash "$HERE/unit.sh"   || status=1; fi
if [[ ($what == all || $what == unit) ]] && command -v dbus-run-session >/dev/null && command -v xfconf-query >/dev/null; then
    bash "$HERE/restore.sh" || status=1
fi
exit $status
