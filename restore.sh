#!/usr/bin/env bash
# restore.sh: undo what these tools' installers changed (the same record and flags as xfce-macos).
#
# Usage:
#   ./restore.sh --list-changes          what was changed, as recorded
#   ./restore.sh --restore               undo it (asks first; --yes skips that)
#   ./restore.sh --restore --dry-run     show what would be undone, change nothing
#   ./restore.sh --restore --packages    also remove the packages the installers added
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/lib/common.sh"
. "$HERE/lib/restore.sh"

usage() { sed -n '/^# Usage:/,/^set -/p' "$0" | sed '$d; s/^# \{0,1\}//'; }

restore=0 list=0 dry=0 pk=() yes=()
for a in "$@"; do
    case "$a" in
        --restore) restore=1 ;;
        --list-changes) list=1 ;;
        --dry-run) dry=1 ;;
        --packages) pk=(--packages) ;;
        --yes|-y) yes=(--yes) ;;
        -h|--help|help) usage; exit 0 ;;
        *) warn "Unknown option: $a"; usage; exit 1 ;;
    esac
done
if (( list )); then lu_restore list "${pk[@]}"; exit; fi
if (( restore )); then
    if (( dry )); then lu_restore dry "${pk[@]}"; else lu_restore run "${pk[@]}" "${yes[@]}"; fi
    exit
fi
(( dry )) && warn "--dry-run goes with --restore"
usage; exit 1
