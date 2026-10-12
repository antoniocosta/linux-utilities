"""vpntray core: parsing of the VPN command-line tool's output and a small provider adapter.

No GUI imports here, so it can be unit-tested without a display. Unofficial; not affiliated
with any VPN provider.
"""
import os
import re
import subprocess
from dataclasses import dataclass, field

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class LinkWatch:
    """Tells when a network interface or address changes: the VPN's tun0 appearing or going, Wi-Fi coming and
    going. `ip monitor` sleeps until the kernel reports a change, so nothing is polled."""
    def __init__(self, cmd=("ip", "monitor", "link", "address")):
        self.proc = subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    def fileno(self):
        return self.proc.stdout.fileno()

    def read(self):
        """The lines that have arrived, or None once the monitor has ended."""
        data = os.read(self.fileno(), 65536)
        return data.decode("utf-8", "replace").splitlines() if data else None

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def strip_ansi(text):
    return ANSI_RE.sub("", text or "")


@dataclass
class Status:
    connected: bool = False
    location: str = ""
    raw: str = ""


@dataclass
class Account:
    logged_in: bool = False
    email: str = ""
    plan: str = ""
    valid_until: str = ""


@dataclass
class Location:
    iso: str
    country: str
    city: str
    ping: int = -1  # milliseconds; -1 when unknown

    @property
    def flag(self):
        """Flag emoji from the two-letter ISO code (empty if it is not one)."""
        iso = self.iso.upper()
        if len(iso) != 2 or not iso.isalpha():
            return ""
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)


@dataclass
class Result:
    ok: bool
    out: str = ""
    err: str = ""

    @property
    def message(self):
        """First useful line of output, for showing inline."""
        text = (self.err or self.out).strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[0] if lines else ""


def parse_status(text):
    """Defensive: only 'disconnected' / 'connected' are known to exist."""
    clean = strip_ansi(text).strip()
    low = clean.lower()
    if not clean or "disconnected" in low or "not connected" in low:
        return Status(False, "", clean)
    if "connected" not in low:
        return Status(False, "", clean)
    loc = ""
    m = re.search(r"connected to\s+(.+?)(?:\s+in\s+\w+\s+mode|,?\s+running on\b.*|\s*$)",
                  clean, re.IGNORECASE | re.MULTILINE)
    if m:
        loc = m.group(1).strip().rstrip(".,")
    else:
        m = re.search(r"^\s*location\s*:\s*(.+)$", clean, re.IGNORECASE | re.MULTILINE)
        if m:
            loc = m.group(1).strip()
    return Status(True, loc, clean)


def parse_license(text):
    clean = strip_ansi(text)
    m = re.search(r"Logged in as\s+(\S+)", clean)
    if not m:
        return Account(False)
    plan = ""
    p = re.search(r"using the\s+(.+?)\s+version", clean, re.IGNORECASE)
    if p:
        plan = p.group(1).strip().title()
    v = re.search(r"valid until\s+(\S+)", clean, re.IGNORECASE)
    return Account(True, m.group(1).strip().rstrip(".,"), plan, v.group(1) if v else "")


def parse_locations(text):
    """Table 'ISO COUNTRY CITY PING ESTIMATE' (sorted by ping by the tool)."""
    lines = strip_ansi(text).splitlines()
    cols = None
    out = []
    for line in lines:
        if cols is None and "ISO" in line and "COUNTRY" in line and "CITY" in line:
            cols = (line.index("COUNTRY"), line.index("CITY"),
                    line.index("PING") if "PING" in line else len(line))
            continue
        if not re.match(r"^[A-Z]{2}\s", line):
            continue
        iso = line[:2]
        fields = None
        if cols:
            a, b, c = cols
            country, city, ping = line[a:b].strip(), line[b:c].strip(), line[c:].strip()
            # sliced columns are only trusted when they fit the row's visible gaps
            if country and city and re.match(r"^\d+", ping) and line[a - 1:a].isspace() \
                    and line[b - 1:b].isspace():
                fields = (country, city, ping)
        if fields is None:
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) < 3:
                continue
            fields = (parts[1], parts[2], parts[3] if len(parts) > 3 else "")
        pm = re.match(r"\d+", fields[2])
        out.append(Location(iso, fields[0], fields[1], int(pm.group()) if pm else -1))
    return out


def parse_exclusions(text):
    """`site-exclusions show`: a header ("Exclusions for GENERAL mode:") and one entry per line.
    Returns (mode, [entries])."""
    mode, items = "general", []
    for line in strip_ansi(text).splitlines():
        m = re.match(r"^\s*Exclusions for (\w+) mode", line)
        if m:
            mode = m.group(1).lower()
            continue
        s = re.sub(r"^[-*\u2022]\s+", "", line.strip())      # a bullet, but not the * of "*.example.com"
        if s and not s.lower().startswith(("you can", "no exclusions", "there are no")):
            items.append(s)
    return mode, items


@dataclass
class Config:
    mode: str = "tun"            # tun / socks
    protocol: str = "auto"       # auto / http2 / quic
    dns: str = "default"
    post_quantum: bool = True
    notifications: bool = False
    change_system_dns: bool = False


def parse_config(text):
    """`config show`: indented "Key: value" lines (values like "Default (on)")."""
    kv = {}
    for line in strip_ansi(text).splitlines():
        m = re.match(r"^\s*([A-Za-z][^:]*):\s*(.*)$", line)
        if m:
            kv[m.group(1).strip().lower()] = m.group(2).strip()

    def onoff(key, dflt):
        m = re.search(r"\b(on|off)\b", kv.get(key, ""), re.I)
        return m.group(1).lower() == "on" if m else dflt

    c = Config()
    if kv.get("mode", "").lower() in ("tun", "socks"):
        c.mode = kv["mode"].lower()
    m = re.search(r"(auto|http2|quic)", kv.get("protocol", ""), re.I)
    c.protocol = m.group(1).lower() if m else "auto"
    dns = kv.get("dns upstream", "")
    c.dns = "default" if not dns or dns.lower().startswith("default") else dns
    c.post_quantum = onoff("post-quantum cryptography", True)
    c.notifications = onoff("show notifications", False)
    c.change_system_dns = onoff("change system dns", False)
    return c


def tun_traffic(iface="tun0", base="/sys/class/net"):
    """(received, sent) bytes through the tunnel since it came up, from the kernel's counters; None if no tunnel."""
    try:
        with open(f"{base}/{iface}/statistics/rx_bytes") as f:
            rx = int(f.read())
        with open(f"{base}/{iface}/statistics/tx_bytes") as f:
            tx = int(f.read())
        return rx, tx
    except (OSError, ValueError):
        return None


def human_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def human_duration(seconds):
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h} h {m:02d} min" if h else (f"{m} min {s:02d} s" if m else f"{s} s")


def service_uptime(proc="/proc"):
    """Seconds since the VPN service started (the oldest process whose name begins with "adguard"), or None."""
    try:
        with open(f"{proc}/uptime") as f:
            up = float(f.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK")
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except (OSError, ValueError):
        return None
    best = None
    for pid in pids:
        try:
            with open(f"{proc}/{pid}/comm") as f:
                if not f.read().strip().lower().startswith("adguard"):
                    continue
            with open(f"{proc}/{pid}/stat") as f:
                start = int(f.read().rsplit(")", 1)[1].split()[19]) / hz   # field 22: when it started
        except (OSError, ValueError, IndexError):
            continue
        age = up - start
        if best is None or age > best:
            best = age
    return best


def state_path():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "vpntray.json")


def load_state():
    import json
    try:
        with open(state_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    import json
    try:
        os.makedirs(os.path.dirname(state_path()), exist_ok=True)
        with open(state_path(), "w") as f:
            json.dump(state, f)
    except OSError:
        pass


class AdGuard:
    """Adapter for the AdGuard VPN command-line tool (unofficial)."""

    name = "AdGuard VPN"

    def __init__(self, cmd="adguardvpn-cli", askpass=None):
        self.cmd = cmd
        self.askpass = askpass

    def run(self, args, stdin=None, timeout=20):
        env = dict(os.environ, NO_COLOR="1")
        if self.askpass:
            env["SUDO_ASKPASS"] = self.askpass
        try:
            p = subprocess.run([self.cmd, *args], input=stdin, capture_output=True, text=True,
                               timeout=timeout, env=env, start_new_session=True,
                               stdin=None if stdin is not None else subprocess.DEVNULL)
        except FileNotFoundError:
            return Result(False, "", f"'{self.cmd}' was not found")
        except subprocess.TimeoutExpired:
            return Result(False, "", "The command timed out")
        return Result(p.returncode == 0, strip_ansi(p.stdout), strip_ansi(p.stderr))

    def status(self):
        r = self.run(["status"])
        return parse_status(r.out) if r.ok or r.out else Status(False, "", r.message)

    def account(self):
        return parse_license(self.run(["license"]).out)

    def locations(self):
        return parse_locations(self.run(["list-locations", "500"], timeout=30).out)

    def connect(self, location=None):
        args = ["connect", "-y"] + (["-l", location] if location else ["-f"])
        return self.run(args, timeout=90)

    def disconnect(self):
        return self.run(["disconnect"], timeout=30)

    def login(self, email, password):
        """The password goes to the tool's stdin only; nothing is stored here."""
        return self.run(["login"], stdin=f"{email}\n{password}\n", timeout=30)

    def logout(self):
        return self.run(["logout"])

    # ---- exclusions ----
    def exclusions(self):
        r = self.run(["site-exclusions", "show"])
        return parse_exclusions(r.out)

    def add_exclusions(self, items):
        return self.run(["site-exclusions", "add", *items])

    def remove_exclusions(self, items):
        return self.run(["site-exclusions", "remove", *items])

    def clear_exclusions(self):
        return self.run(["site-exclusions", "clear"])

    def set_exclusion_mode(self, mode):
        return self.run(["site-exclusions", "mode", mode])

    # ---- settings ----
    SETTERS = {"mode": "set-mode", "protocol": "set-protocol", "dns": "set-dns",
               "post_quantum": "set-post-quantum", "notifications": "set-show-notifications",
               "change_system_dns": "set-change-system-dns"}

    def config(self):
        return parse_config(self.run(["config", "show"]).out)

    def set_config(self, key, value):
        if isinstance(value, bool):
            value = "on" if value else "off"
        return self.run(["config", self.SETTERS[key], str(value)])

    # ---- support ----
    def version(self):
        r = self.run(["--version"])
        return (r.out or r.err).strip()

    def export_logs(self, folder):
        return self.run(["export-logs", "-o", folder, "-f"], timeout=60)

    def check_update(self):
        return self.run(["check-update"], timeout=40)
