"""Offline checks only: no TV connection, USB mount, formatting, or exploit execution."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import unittest
from unittest import mock
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("usb_check", ROOT / "scripts" / "launch-usb-check.py")
usb_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usb_check)
SECRET = "FAKE-private-pairing-token"


class UsbProbeTests(unittest.TestCase):
    def test_cgi_is_syntax_valid_and_contains_only_fixed_identity_reads(self):
        script = ROOT / "usb-probe" / "quietframe-identity.cgi"
        subprocess.run(["/bin/sh", "-n", str(script)], check=True, capture_output=True)
        content = script.read_text()
        self.assertNotIn("$", content)
        self.assertNotIn("`", content)
        calls = []
        for line in content.splitlines():
            if line.startswith("#!") or not line.strip():
                continue
            args = shlex.split(line)
            if args[0] == "printf":
                self.assertEqual(len(args), 2)
            else:
                self.assertIn(args, [["id", "-u"], ["uname", "-s"], ["uname", "-m"]])
                calls.append(args)
        self.assertEqual(len(calls), 3)
        self.assertIn("QUIETFRAME_IDENTITY_BEGIN", content)
        self.assertIn("QUIETFRAME_IDENTITY_END", content)

    def test_static_marker_has_no_active_content(self):
        html = (ROOT / "usb-probe" / "quietframe-usb-marker.html").read_text()
        self.assertIn("QUIETFRAME_USB_MARKER_V1", html)
        for forbidden in ["<script", "<iframe", "<img", "http://", "https://", "onload="]:
            self.assertNotIn(forbidden, html.lower())

    def test_launch_modes_use_only_the_reviewed_targets_and_paired_api(self):
        for mode in ["marker", "identity"]:
            opener = mock.Mock()
            opener.open.return_value = io.BytesIO(b'{"STATUS":{"RESULT":"SUCCESS"}}')
            output = io.StringIO()
            with mock.patch.dict(usb_check.os.environ, {"TV_IP": "192.168.1.50", "VIZIO_TOKEN": SECRET}, clear=True), \
                 mock.patch.object(usb_check.urllib.request, "build_opener", return_value=opener) as build, \
                 contextlib.redirect_stdout(output):
                usb_check.main(["--" + mode])
            opener.open.assert_called_once()
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://192.168.1.50:7345/app/launch")
            self.assertEqual(request.method, "PUT")
            self.assertEqual(request.get_header("Auth"), SECRET)
            self.assertEqual(json.loads(request.data), {"VALUE": {
                "NAME_SPACE": 4, "APP_ID": "17", "MESSAGE": usb_check.TARGETS[mode]}})
            self.assertNotIn(SECRET, output.getvalue())
            handlers = build.call_args.args
            self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler) and h.proxies == {} for h in handlers))
            redirect = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
            self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid/"))

    def test_requires_explicit_mode_and_rejects_arbitrary_url_or_command(self):
        for args in [[], ["--url", "https://example.invalid/"], ["--command", "id"], ["--marker", "--identity"]]:
            with contextlib.redirect_stderr(io.StringIO()), \
                 mock.patch.object(usb_check.urllib.request, "build_opener") as build:
                with self.assertRaises(SystemExit):
                    usb_check.main(args)
                build.assert_not_called()

    def test_public_destination_is_rejected_without_network(self):
        with mock.patch.dict(usb_check.os.environ, {"TV_IP": "8.8.8.8", "VIZIO_TOKEN": SECRET}, clear=True), \
             mock.patch.object(usb_check.urllib.request, "build_opener") as build:
            with self.assertRaisesRegex(SystemExit, "private LAN"):
                usb_check.main(["--marker"])
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
