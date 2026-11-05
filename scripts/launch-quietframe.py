#!/usr/bin/env python3
"""One-shot paired launch. No server, token files, or response-body logging."""

import getpass
import ipaddress
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    host = os.environ.get("TV_IP") or input("TV's LAN IP address: ").strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise SystemExit("Use the TV's numeric LAN IP address.")
    if not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise SystemExit("Use the TV's private LAN address.")
    url = input("QuietFrame HTTPS URL: ").strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SystemExit("Use an HTTPS URL without embedded credentials.")
    token = os.environ.get("VIZIO_TOKEN") or getpass.getpass("External pairing token (hidden): ")
    if not token:
        raise SystemExit("A pairing token is required. Nothing was sent.")
    payload = {"VALUE": {"MESSAGE": url, "NAME_SPACE": 4, "APP_ID": "17"}}
    authority = "[" + host + "]" if address.version == 6 else host
    request = urllib.request.Request(
        "https://" + authority + ":7345/app/launch",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "AUTH": token},
        method="PUT",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    # Equivalent to the project's existing curl -k: the paired LAN service uses
    # a certificate that fails normal hostname validation. This changes no TV setting.
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
    print("Launch accepted. Confirm QuietFrame appears on the TV. This program now exits.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("Launch cancelled.")
