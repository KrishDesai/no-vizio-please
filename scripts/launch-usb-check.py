#!/usr/bin/env python3
"""Launch one of two fixed TV-local USB checks; no installer or arbitrary command.

Identity mode is an exploit-based compatibility experiment. Review
USB_PROBE_ASSESSMENT.md and obtain the owner's explicit approval first.
"""

import argparse
import getpass
import ipaddress
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

TARGETS = {
    "marker": "http://127.0.0.1:12345/usbparts/sda1/quietframe-usb-marker.html",
    "identity": "http://127.0.0.1:12345/usbparts/sda1/quietframe-identity.cgi",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch a fixed QuietFrame USB check. Review USB_PROBE_ASSESSMENT.md first.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--marker", action="store_true", help="Show the static USB marker only.")
    modes.add_argument("--identity", action="store_true", help="Owner-approved identity-only CGI test; run only after the marker passes.")
    args = parser.parse_args(argv)
    target = TARGETS["identity" if args.identity else "marker"]
    host = os.environ.get("TV_IP") or input("TV's current LAN IP address: ").strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise SystemExit("Use the TV's numeric private LAN IP.")
    if not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise SystemExit("Use the TV's private LAN IP.")
    token = os.environ.get("VIZIO_TOKEN")
    if not token:
        if not sys.stdin.isatty():
            raise SystemExit("Use an interactive Terminal for the hidden pairing-token prompt.")
        token = getpass.getpass("External pairing token (hidden): ")
    if not token:
        raise SystemExit("No token supplied; nothing sent.")
    authority = "[" + host + "]" if address.version == 6 else host
    payload = {"VALUE": {"NAME_SPACE": 4, "APP_ID": "17", "MESSAGE": target}}
    request = urllib.request.Request(
        "https://" + authority + ":7345/app/launch",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "AUTH": token},
        method="PUT",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
        NoRedirect(),
    )
    try:
        with opener.open(request, timeout=10) as response:
            data = json.loads(response.read(1024 * 1024))
    except (urllib.error.URLError, OSError, ValueError):
        raise SystemExit("No readable launch result. Check the TV before retrying; no response body was logged.")
    if not isinstance(data, dict) or not isinstance(data.get("STATUS"), dict) or data["STATUS"].get("RESULT") != "SUCCESS":
        raise SystemExit("The TV did not report SUCCESS. No response body was logged.")
    print("Launch accepted. Check the TV screen; acceptance alone does not prove USB access or CGI execution.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("USB check cancelled.")
