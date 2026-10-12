# Linux Utilities

Small, light utilities for Linux desktops, one folder each. They sit beside
[xfce-macos](https://github.com/antoniocosta/xfce-macos), which makes Xfce feel like macOS, and work
on their own too.

If you like this or find it useful, support the project by buying me a coffee.

<a href="https://www.buymeacoffee.com/antoniocosta" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 140px !important;" ></a>

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

A top-bar mask (green when connected, dimmed when not) whose menu is laid out like the macOS
AdGuard VPN app's:

```
Status: Disconnected
Location: Switzerland, Zurich
-----
Connect
Disconnect
-----
Connect to >   (the fastest locations with their flags, and "Other servers..." at the bottom)
-----
Open AdGuard VPN
Exclusions
Stats
Support
Settings
-----
Quit AdGuard VPN
```

and a compact panel with the same tabs:

- **Home**: the connect switch with the status and location, a "Fastest location" row, and a
  searchable list of every location (flag, city, ping); a login form when logged out.
- **Exclusions**: General or Selective mode, and the sites (`example.com`, `*.example.com`, an IP
  address) to add or remove.
- **Stats**: connected time and the traffic through the tunnel (downloaded, uploaded), refreshed
  every 2 seconds while the tab is showing.
- **Support**: the tool's version, the support page, *Export logs* (to Downloads) and *Check for
  updates*.
- **Settings**: your account (with Log out), the mode (TUN or SOCKS5), the protocol (Automatic,
  HTTP/2, QUIC), the DNS upstream, post-quantum encryption, changing the system's DNS, and
  connection notifications. These are the tool's own `config` settings.

Errors show inline; the panel hides when it loses focus. Choose any of the menu entries (or
middle-click the mask for *Connect to*); running `vpntray` also opens the panel, and
`vpntray --tab=exclusions` opens a given tab. The mask is a generic mask drawn for this project,
not AdGuard's logo.

It drives the AdGuard VPN command-line tool (`adguardvpn-cli`, installed separately) and is
**unofficial and not affiliated with AdGuard**. Python 3 + GTK3, about 30 MB, 0% CPU when idle:
no timers; the status is read at start, when the panel opens, after each action, and whenever the
network changes (it listens to `ip monitor`, so the mask also follows a VPN connected or dropped
from the command line or by a reconnect). Your
password goes only to the tool's standard input; nothing is stored. Connecting in TUN mode needs
root, so vpntray points `SUDO_ASKPASS` at a small password dialog (zenity). No sudoers rule.

`./vpntray/install.sh`. Tests, without a VPN or display (a fake command-line tool):
`python3 vpntray/test_vpntray.py`; `vpntray/smoke-test.sh` opens every tab on a private invisible
display and fails on any error.

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
