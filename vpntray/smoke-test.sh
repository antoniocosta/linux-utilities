#!/usr/bin/env bash
# Starts vpntray on a private invisible display (Xvfb, its own D-Bus session, its own HOME) against the
# fake command-line tool, opens every tab, and fails on any Python error or GTK critical message.
# Nothing touches your session. Prints "ok" or what went wrong.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${VT_SMOKE_INSIDE:-}" ]]; then
    exec env VT_SMOKE_INSIDE=1 PATH="$PATH" dbus-run-session -- bash "$0"
fi

tmp="$(mktemp -d)"
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/c" XDG_STATE_HOME="$tmp/s" XDG_CACHE_HOME="$tmp/k"
mkdir -p "$HOME"
export GTK_USE_PORTAL=0 GIO_USE_PORTAL=0 NO_AT_BRIDGE=1 GIO_USE_VFS=local     # no desktop portals / keyring waiting
export FAKE_VPN_DIR="$tmp/vpn" VPNTRAY_CLI="$HERE/fake-adguardvpn-cli"
mkdir -p "$FAKE_VPN_DIR"
echo "me@example.com" > "$FAKE_VPN_DIR/user"
printf 'a.com\n*.b.com\n' > "$FAKE_VPN_DIR/exclusions"

for n in $(seq 120 160); do [[ -e /tmp/.X11-unix/X$n ]] || { dnum=$n; break; }; done
Xvfb ":$dnum" -screen 0 1000x700x24 -nolisten tcp >/dev/null 2>&1 &
xpid=$!
export DISPLAY=":$dnum"
cleanup() { kill "${app:-0}" "$xpid" 2>/dev/null; sleep 0.3; kill -9 "${app:-0}" "$xpid" 2>/dev/null; rm -rf "$tmp"; }
trap cleanup EXIT
for _ in $(seq 40); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done

log="$tmp/err.txt"
python3 "$HERE/vpntray" --background >"$log" 2>&1 &
app=$!
sleep 2.5
for tab in home exclusions stats support settings home; do
    python3 "$HERE/vpntray" --tab="$tab" >>"$log" 2>&1
    sleep 0.5
    kill -0 "$app" 2>/dev/null || { echo "RESULT: the app died on the $tab tab"; cat "$log"; exit 1; }
done

if grep -E "Traceback|Error:|CRITICAL|assertion" "$log" >/dev/null; then
    echo "RESULT: errors while opening the tabs:"; grep -E -B2 -A6 "Traceback|Error:|CRITICAL|assertion" "$log" | head -30
    exit 1
fi
echo "RESULT: ok"
