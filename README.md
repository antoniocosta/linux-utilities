# Linux Utilities

Small, light utilities for Linux desktops, one folder each. They sit beside
[xfce-macos](https://github.com/antoniocosta/xfce-macos), which makes Xfce feel like macOS, and work
on their own too.

| Utility | What it does |
|---|---|
| [net-badge](#net-badge) | Network latency in the menu bar ("● 24 ms"), with a popover. Xfce panel. |
| [vpntray](#vpntray) | Top-bar VPN panel in the style of the macOS menu-bar app: connect toggle, fastest, searchable locations with ping, account and login. |
| [ssh-keyring](#ssh-keyring) | Unlocks your SSH key at login from the login keyring, like the macOS Keychain. |

Each has its own `install.sh`, which is safe to re-run. Programs go in `~/.local/bin`; settings
in your Xfce settings and `~/.config`. Where a file is shared with other tools, the change sits in
a marked block that a re-run replaces instead of duplicating.

```
git clone https://github.com/antoniocosta/linux-utilities.git
cd linux-utilities
./net-badge/install.sh          # or ./vpntray/install.sh, ./ssh-keyring/install.sh
```

**Undo:** `./restore.sh --list-changes` shows what the installers recorded, `./restore.sh --restore`
undoes it (asks first; `--dry-run` previews, `--packages` also removes packages they added).

---

## net-badge

A coloured dot and the current latency in the menu bar, measured every 5 seconds as one TCP
handshake to Apple's captive-portal server. Colours follow
[Network Badge](https://github.com/Someniak/macos-network-badge)'s tiers (< 30 / 80 / 150 /
300 ms). The tooltip and a click popover show the connection, Wi-Fi name, a sparkline of the
last 3 minutes and min/avg/max; a notification appears when the connection turns poor. Runs in
Xfce's Generic Monitor plugin, so there's no extra process between measurements.

---

## vpntray

A top-bar shield (outline: off, filled: on) with a compact panel like the macOS VPN menu-bar
apps: a connect switch with the status and location, a "Fastest location" row, a searchable list
of locations (flag, city, ping), your account with Log out, and a login form when logged out.
Errors show inline; the panel hides when it loses focus. Click the shield and choose
*Open panel* (or middle-click it; running `vpntray` also opens it).

It drives the AdGuard VPN command-line tool (`adguardvpn-cli`, installed separately) and is
**unofficial and not affiliated with AdGuard**. Python 3 + GTK3, about 30 MB, 0% CPU when idle:
no timers; the status is read at start, when the panel opens and after each action. Your
password goes only to the tool's standard input; nothing is stored. Connecting in TUN mode needs
root, so vpntray points `SUDO_ASKPASS` at a small password dialog (zenity). No sudoers rule.

`./vpntray/install.sh`. Tests, without a VPN or display (a fake command-line tool):
`python3 vpntray/test_vpntray.py`.

---

## ssh-keyring

On macOS the Keychain unlocks your SSH key when you log in. This does the same with the login
keyring: the passphrase is stored there once, and at login `ssh-keyring unlock` adds the key to
the session's ssh-agent. The key file stays encrypted on disk, and the passphrase never appears
on a command line.

```
./ssh-keyring/install.sh [KEY]   # default ~/.ssh/id_ed25519
ssh-keyring store                  # once: type the passphrase; it's checked, then saved
ssh-keyring forget                 # remove it from the keyring
```

---

# Extras

## Tests

```
tests/run.sh             # everything
tests/run.sh static      # scripts parse and pass shellcheck, nothing private, README complete
tests/run.sh unit        # the installers' helpers, the change record with --restore, vpntray's parsers
```

The restore tests run in a temporary home with their own D-Bus session; `sudo`, `systemctl` and `apt-get`
are stubs, so nothing touches your real system or settings.

## License

MIT, see [LICENSE](LICENSE).
