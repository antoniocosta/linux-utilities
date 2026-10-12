#!/usr/bin/env python3
"""Unit tests for vpntray's parsing and CLI adapter. No VPN, no display: uses fake-adguardvpn-cli.
Run: python3 extras/vpntray/test_vpntray.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import vpntray_core as core  # noqa: E402

B, R = "\x1b[1m", "\x1b[0m"
TABLE = (f"{B}ISO   COUNTRY              CITY                           PING ESTIMATE\n{R}"
         "NL    Netherlands          Amsterdam                      24        \n"
         "US    United States        New York                       95        \n"
         "ZA    South Africa         Johannesburg                   -         \n\n"
         "You can connect to a location by running `x connect -l 'city'`\n")
LICENSE = (f"Logged in as {B}someone@example.com{R}\nYou are using the {B}PREMIUM{R} version\n"
           f"Up to {B}10{R} devices simultaneously\nYour subscription is valid until 2030-01-31\n")


class Parse(unittest.TestCase):
    def test_ansi(self):
        self.assertEqual(core.strip_ansi(f"{B}bold{R} plain"), "bold plain")
        self.assertEqual(core.strip_ansi(None), "")

    def test_status_disconnected(self):
        s = core.parse_status("VPN is disconnected\nYou can connect to a location by running `x`\n")
        self.assertFalse(s.connected)
        self.assertEqual(s.location, "")

    def test_status_empty_and_garbage(self):
        self.assertFalse(core.parse_status("").connected)
        self.assertFalse(core.parse_status("something unexpected").connected)

    def test_status_connected_variants(self):
        s = core.parse_status(f"Connected to {B}AMSTERDAM, Netherlands{R} in TUN mode, running on tun0\n")
        self.assertTrue(s.connected)
        self.assertEqual(s.location, "AMSTERDAM, Netherlands")
        s = core.parse_status("VPN is connected to Tokyo, Japan\n")
        self.assertTrue(s.connected)
        self.assertEqual(s.location, "Tokyo, Japan")
        s = core.parse_status("Connected\nLocation: Oslo\n")
        self.assertTrue(s.connected)
        self.assertEqual(s.location, "Oslo")
        s = core.parse_status("VPN is connected")  # unknown format: still "on", no location
        self.assertTrue(s.connected)
        self.assertEqual(s.location, "")

    def test_license(self):
        a = core.parse_license(LICENSE)
        self.assertTrue(a.logged_in)
        self.assertEqual((a.email, a.plan, a.valid_until), ("someone@example.com", "Premium", "2030-01-31"))

    def test_license_logged_out(self):
        self.assertFalse(core.parse_license("You are not logged in.\n").logged_in)
        self.assertFalse(core.parse_license("").logged_in)

    def test_locations(self):
        locs = core.parse_locations(TABLE)
        self.assertEqual([l.iso for l in locs], ["NL", "US", "ZA"])
        self.assertEqual((locs[1].country, locs[1].city, locs[1].ping), ("United States", "New York", 95))
        self.assertEqual(locs[2].ping, -1)
        self.assertEqual(locs[0].flag, "\U0001F1F3\U0001F1F1")

    def test_locations_without_header_and_empty(self):
        locs = core.parse_locations("NL    Netherlands    Amsterdam    24\n")
        self.assertEqual((locs[0].country, locs[0].city, locs[0].ping), ("Netherlands", "Amsterdam", 24))
        self.assertEqual(core.parse_locations(""), [])

    def test_result_message(self):
        self.assertEqual(core.Result(False, "", "\nError: nope\nmore").message, "Error: nope")


class Adapter(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        os.environ["FAKE_VPN_DIR"] = self.d.name
        self.vpn = core.AdGuard(os.path.join(HERE, "fake-adguardvpn-cli"))

    def tearDown(self):
        self.d.cleanup()
        os.environ.pop("FAKE_VPN_DIR", None)
        os.environ.pop("FAKE_FAIL", None)

    def calls(self):
        with open(os.path.join(self.d.name, "calls")) as f:
            return f.read().splitlines()

    def test_login_flow(self):
        self.assertFalse(self.vpn.account().logged_in)
        self.assertFalse(self.vpn.login("a@example.com", "wrong").ok)
        self.assertEqual(self.vpn.login("a@example.com", "pw").ok, True)
        self.assertEqual(self.vpn.account().email, "a@example.com")
        self.assertEqual(self.vpn.account().plan, "Premium")
        self.assertTrue(self.vpn.logout().ok)
        self.assertFalse(self.vpn.account().logged_in)

    def test_connect_disconnect(self):
        self.vpn.login("a@example.com", "pw")
        self.assertFalse(self.vpn.status().connected)
        self.assertTrue(self.vpn.connect().ok)
        self.assertEqual(self.calls()[-1], "connect -y -f")
        self.assertTrue(self.vpn.status().connected)
        self.assertTrue(self.vpn.connect("Tokyo").ok)
        self.assertEqual(self.calls()[-1], "connect -y -l Tokyo")
        self.assertEqual(self.vpn.status().location, "Tokyo")
        self.assertTrue(self.vpn.disconnect().ok)
        self.assertFalse(self.vpn.status().connected)

    def test_failure_is_reported(self):
        self.vpn.login("a@example.com", "pw")
        os.environ["FAKE_FAIL"] = "boom"
        r = self.vpn.connect()
        self.assertFalse(r.ok)
        self.assertEqual(r.message, "Error: boom")

    def test_locations(self):
        self.assertEqual(len(self.vpn.locations()), 3)

    def test_password_not_in_arguments(self):
        self.vpn.login("a@example.com", "s3cret")
        self.assertNotIn("s3cret", "\n".join(self.calls()))

    def test_missing_cli(self):
        r = core.AdGuard("/nonexistent/vpn-cli").run(["status"])
        self.assertFalse(r.ok)
        self.assertIn("not found", r.message)

    def test_askpass_exported(self):
        v = core.AdGuard("/usr/bin/env", askpass="/x/askpass")
        self.assertIn("SUDO_ASKPASS=/x/askpass", v.run([]).out)


REAL_CONFIG = """Current configuration:
\tData directory: /home/user/.local/share/adguardvpn-cli
\tMode: tun
\tSOCKS port: 1080
\tDNS upstream: Default (provided by AdGuard VPN)
\tTunnel routing mode: auto
\tChange system DNS: off
\tProtocol: Default (auto)
\tPost-quantum cryptography: Default (on)
\tShow notifications: Default (off)
"""


class TestSettingsAndExclusions(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["FAKE_VPN_DIR"] = self.dir
        self.v = core.AdGuard(os.path.join(HERE, "fake-adguardvpn-cli"))

    def test_parse_exclusions(self):
        self.assertEqual(core.parse_exclusions("Exclusions for GENERAL mode:\n\n"), ("general", []))
        self.assertEqual(core.parse_exclusions("Exclusions for SELECTIVE mode:\n*.a.com\nb.com\n"),
                         ("selective", ["*.a.com", "b.com"]))
        self.assertEqual(core.parse_exclusions("Exclusions for GENERAL mode:\n- x.com\n* y.com\n")[1], ["x.com", "y.com"])

    def test_exclusions_round_trip(self):
        self.assertEqual(self.v.exclusions(), ("general", []))
        self.assertTrue(self.v.add_exclusions(["a.com", "*.b.com"]).ok)
        self.assertEqual(sorted(self.v.exclusions()[1]), ["*.b.com", "a.com"])
        self.v.remove_exclusions(["a.com"])
        self.assertEqual(self.v.exclusions()[1], ["*.b.com"])
        self.v.set_exclusion_mode("selective")
        self.assertEqual(self.v.exclusions()[0], "selective")
        self.v.clear_exclusions()
        self.assertEqual(self.v.exclusions()[1], [])

    def test_parse_config_real_output(self):
        c = core.parse_config(REAL_CONFIG)
        self.assertEqual((c.mode, c.protocol, c.dns), ("tun", "auto", "default"))
        self.assertTrue(c.post_quantum)
        self.assertFalse(c.notifications)
        self.assertFalse(c.change_system_dns)

    def test_parse_config_values(self):
        c = core.parse_config("\tMode: socks\n\tDNS upstream: 9.9.9.9\n\tProtocol: QUIC\n"
                              "\tPost-quantum cryptography: off\n\tShow notifications: on\n")
        self.assertEqual((c.mode, c.protocol, c.dns), ("socks", "quic", "9.9.9.9"))
        self.assertFalse(c.post_quantum)
        self.assertTrue(c.notifications)

    def test_set_config(self):
        self.assertTrue(self.v.set_config("protocol", "quic").ok)
        self.assertTrue(self.v.set_config("post_quantum", False).ok)
        c = self.v.config()
        self.assertEqual(c.protocol, "quic")
        self.assertFalse(c.post_quantum)
        self.v.set_config("notifications", True)
        self.assertTrue(self.v.config().notifications)

    def test_support(self):
        self.assertIn("9.9.9", self.v.version())
        r = self.v.export_logs(self.dir)
        self.assertTrue(r.ok)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "adguard_vpn_logs.zip")))
        self.assertIn("latest", self.v.check_update().out)

    def test_traffic_and_units(self):
        base = tempfile.mkdtemp()
        os.makedirs(f"{base}/tun0/statistics")
        open(f"{base}/tun0/statistics/rx_bytes", "w").write("1048576\n")
        open(f"{base}/tun0/statistics/tx_bytes", "w").write("2048\n")
        self.assertEqual(core.tun_traffic("tun0", base), (1048576, 2048))
        self.assertIsNone(core.tun_traffic("tun9", base))
        self.assertEqual(core.human_bytes(512), "512 B")
        self.assertEqual(core.human_bytes(1048576), "1.0 MB")
        self.assertEqual(core.human_duration(75), "1 min 15 s")
        self.assertEqual(core.human_duration(7500), "2 h 05 min")


class TestLinkWatch(unittest.TestCase):
    def test_lines_arrive_as_they_happen(self):
        import select
        w = core.LinkWatch(("sh", "-c", "echo '5: tun0: <UP>'; sleep 0.3; echo '5: tun0: <DOWN>'; sleep 0.3"))
        got = []
        for _ in range(10):
            ready, _, _ = select.select([w.fileno()], [], [], 2)
            if not ready:
                break
            lines = w.read()
            if lines is None:
                break
            got += lines
        w.close()
        self.assertEqual(got, ["5: tun0: <UP>", "5: tun0: <DOWN>"])

    def test_ends_with_none(self):
        w = core.LinkWatch(("true",))
        w.proc.wait()
        self.assertIsNone(w.read())
        w.close()

    def test_missing_command(self):
        with self.assertRaises(OSError):
            core.LinkWatch(("/nonexistent/ip-monitor",))


if __name__ == "__main__":
    unittest.main()
