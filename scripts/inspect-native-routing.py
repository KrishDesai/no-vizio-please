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
import urllib.parse
import urllib.request

READS = (
    ("GET", "/app/current", None),
    ("PUT", "/app/config/get_property", "SmartCastHome"),
    ("PUT", "/app/config/get_property", "AppConfigs"),
    ("PUT", "/app/config/get_property", "VIZIOApps"),
)
SAFE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}\Z")
CANDIDATE_KEY = re.compile(r"home(?!kit)|boot|startup|autostart|launcher|conjure|framework", re.I)
SENSITIVE_KEY = re.compile(r"auth|token|secret|password|pwd|cookie|session|credential|signature|dsk|sns|salt|user|account|device|serial|esn|dsn|ssid|email|api.?key", re.I)


def asset_location(value):
    """Expose only vendor/loopback origins and static asset paths, without queries."""
    if not isinstance(value, str) or len(value) > 2048:
        return {}
    try:
        url = urllib.parse.urlsplit(value)
        host = url.hostname or ""
        if url.scheme not in ("http", "https") or url.username or url.password:
            return {}
        if host not in ("127.0.0.1", "localhost", "::1", "vizio.com") and not host.endswith((".vizio.com", ".vizio.tv", ".viziocdn.com", ".vzolab.com")):
            return {}
        origin = url.scheme + "://" + ("[" + host + "]" if ":" in host else host)
        if url.port:
            origin += ":" + str(url.port)
        result = {"source_origin": origin}
        if re.fullmatch(r"/[A-Za-z0-9_./-]{1,400}\.(?:html?|m?js|json|xml|zip|css|wasm)", url.path, re.I):
            result["asset_url"] = origin + url.path
        return result
    except ValueError:
        return {}


def section_structure(value, path=(), depth=0, budget=None):
    """Expand selected configuration sections; never emit arbitrary scalar values."""
    if budget is None:
        budget = [100]
    if depth > 5 or budget[0] <= 0:
        return []
    fields = []
    if isinstance(value, dict):
        children = [(key, value[key]) for key in keys(value)]
    elif isinstance(value, list):
        children = [("[" + str(i) + "]", node) for i, node in enumerate(value[:8])]
    else:
        children = []
    for key, node in children:
        if budget[0] <= 0:
            break
        parts = path + (key,)
        field = {"field": ":".join(parts), "type": type(node).__name__}
        if not any(SENSITIVE_KEY.search(part) for part in parts):
            field.update(asset_location(node))
        fields.append(field)
        budget[0] -= 1
        fields.extend(section_structure(node, parts, depth + 1, budget))
    return fields


def redact_report(value, token):
    if isinstance(value, str):
        return value.replace(token, "[redacted]").replace(urllib.parse.quote(token, safe=""), "[redacted]")
    if isinstance(value, list):
        return [redact_report(item, token) for item in value]
    if isinstance(value, dict):
        return {redact_report(key, token): redact_report(item, token) for key, item in value.items()}
    return value


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
        if isinstance(value, dict):
            result["selected_structure"] = section_structure({key: value[key] for key in
                ("Override", "LocalAssetsUri", "UrlEndpoint", "ServiceMessageRouterUrl") if key in value})
    elif root == "AppConfigs":
        result["root_fields"] = keys(value)
        result["candidate_fields"] = candidate_fields(value)
        if isinstance(value, dict):
            result["selected_structure"] = {key: section_structure(value[key], (key,))
                for key in ("VIZIOHome", "SystemUI") if key in value}
    elif root == "VIZIOApps":
        result["entries"] = []
        for entry in value[:100] if isinstance(value, list) else []:
            if not isinstance(entry, dict):
                continue
            summary = app_summary(entry.get("APP_INFO"))
            if summary is not None:
                cname = entry.get("CNAME")
                if isinstance(cname, str) and SAFE_KEY.fullmatch(cname):
                    summary["CNAME"] = cname
                result["entries"].append(summary)
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
    report = {"inspector_version": 2, "scope": "paired LAN API reads only; no settings changed", "reads": []}
    for method, path, root in READS:
        result = read_config(opener, origin, token, method, path, root)
        report["reads"].append({"path": path, "root": root, **result})
    # Defense against a response reflecting the external token even as a key.
    output = json.dumps(redact_report(report, token), indent=2)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("Inspection cancelled.")
