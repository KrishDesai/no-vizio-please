#!/usr/bin/env python3
"""Bounded configuration reads for QuietFrame research; never writes TV state.

Run while VIZIO Home is visible. No response bodies, store contents, credentials,
or device identifiers are saved. PUT on get_property is a read, as implemented
in the published companion SDK. No bundled SDK or third-party code is executed.
"""

import getpass
import ipaddress
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

READS = (
    ("GET", "/app/current", None),
    ("PUT", "/app/config/get_property", "SmartCastHome"),
    ("PUT", "/app/config/get_property", "AppConfigs"),
    ("PUT", "/app/config/get_property", "VIZIOApps"),
)
SAFE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}\Z")
CANDIDATE_KEY = re.compile(r"home|boot|startup|autostart|launcher|conjure|framework", re.I)


def keys(value):
    if not isinstance(value, dict):
        return []
    return [key for key in value if isinstance(key, str) and SAFE_KEY.fullmatch(key)][:60]


def app_summary(value):
    """Retain numeric app identity and a few structural message fields only."""
    if not isinstance(value, dict):
        return None
    result = {}
    namespace = value.get("NAME_SPACE")
    app_id = value.get("APP_ID")
    if type(namespace) is int and 0 <= namespace <= 99:
        result["NAME_SPACE"] = namespace
    if isinstance(app_id, (str, int)) and re.fullmatch(r"[0-9]{1,8}", str(app_id)):
        result["APP_ID"] = str(app_id)
    message = value.get("MESSAGE")
    if message is None or message == "":
        result["message_kind"] = "empty"
    elif isinstance(message, str):
        try:
            decoded = json.loads(message)
        except ValueError:
            decoded = None
        if isinstance(decoded, dict):
            result["message_kind"] = "JSON object"
            result["message_fields"] = keys(decoded)
            bundle = decoded.get("bundle")
            if isinstance(bundle, str) and re.fullmatch(r"bundles/[a-z0-9/_-]{1,120}", bundle):
                result["bundle"] = bundle
            if decoded.get("app") in ("home", "uml"):
                result["app"] = decoded["app"]
        elif message.startswith(("http://", "https://")):
            result["message_kind"] = "URL (value withheld)"
        else:
            result["message_kind"] = "text (value withheld)"
    else:
        result["message_kind"] = "non-string (value withheld)"
    return result if "APP_ID" in result or "NAME_SPACE" in result else None


def candidate_fields(value, path=(), depth=0):
    """Report key paths and types, never scalar values; keep traversal bounded."""
    found = []
    if not isinstance(value, dict) or depth > 5:
        return found
    for key in keys(value):
        node = value[key]
        parts = path + (key,)
        if CANDIDATE_KEY.search(key):
            found.append({"field": ":".join(parts), "type": type(node).__name__})
        if isinstance(node, dict):
            found.extend(candidate_fields(node, parts, depth + 1))
        if len(found) >= 40:
            break
    return found[:40]


def summarize(data, root):
    if not isinstance(data, dict) or not isinstance(data.get("STATUS"), dict):
        return {"result": "unrecognized response shape"}
    status = data["STATUS"].get("RESULT")
    if status != "SUCCESS":
        return {"result": status if status in ("FAILURE", "INVALID_PARAMETER", "REQUIRES_PAIRING") else "API did not report SUCCESS"}
    item = data.get("ITEM")
    value = item.get("VALUE") if isinstance(item, dict) else None
    if root and isinstance(value, dict) and root in value:
        value = value[root]
    result = {"result": "SUCCESS"}
    if root is None:
        result["current_app"] = app_summary(value)
    elif root == "SmartCastHome":
        result["root_fields"] = keys(value)
        result["home_app"] = app_summary(value.get("AppInfo")) if isinstance(value, dict) else None
        result["candidate_fields"] = candidate_fields(value)
    elif root == "AppConfigs":
        result["root_fields"] = keys(value)
        result["candidate_fields"] = candidate_fields(value)
    elif root == "VIZIOApps":
        result["entries"] = [summary for entry in value[:100]
                             if isinstance(entry, dict) and (summary := app_summary(entry.get("APP_INFO")))] if isinstance(value, list) else []
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_config(opener, origin, token, method, path, root):
    if (method, path, root) not in READS:
        raise ValueError("Request is outside the fixed read-only allowlist")
    headers = {"AUTH": token}
    body = None
    if method == "PUT":
        headers["Content-Type"] = "application/json"
        body = json.dumps({"VALUE": root}).encode("utf-8")
    request = urllib.request.Request(origin + path, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                return {"result": "response exceeds inspection limit"}
            return summarize(json.loads(raw), root)
    except urllib.error.HTTPError as error:
        return {"result": "HTTP " + str(error.code)}
    except (urllib.error.URLError, OSError, ValueError):
        return {"result": "no readable JSON response; details withheld"}


def main():
    host = os.environ.get("TV_IP") or input("TV's LAN IP address: ").strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise SystemExit("Use the TV's numeric private LAN IP.")
    if not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise SystemExit("Use the TV's private LAN IP.")
    token = os.environ.get("VIZIO_TOKEN")
    if not token:
        if not sys.stdin.isatty():
            raise SystemExit("Run in an interactive Terminal for the hidden token prompt.")
        token = getpass.getpass("External pairing token (hidden): ")
    if not token:
        raise SystemExit("No token supplied; nothing sent.")
    authority = "[" + host + "]" if address.version == 6 else host
    origin = "https://" + authority + ":7345"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
        NoRedirect(),
    )
    report = {"scope": "paired LAN API reads only; no settings changed", "reads": []}
    for method, path, root in READS:
        result = read_config(opener, origin, token, method, path, root)
        report["reads"].append({"path": path, "root": root, **result})
    # Defense against a response reflecting the external token even as a key.
    output = json.dumps(report, indent=2).replace(token, "[redacted]")
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("Inspection cancelled.")
