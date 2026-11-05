"""The native-routing inspector must issue configuration reads only."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock
import urllib.error
import urllib.request

SPEC = importlib.util.spec_from_file_location(
    "inspector", Path(__file__).resolve().parents[1] / "scripts" / "inspect-native-routing.py"
)
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)
SECRET = "FAKE-private-pairing-token"


def response(value):
    return io.BytesIO(json.dumps({"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": value}}).encode())


class InspectorTests(unittest.TestCase):
    def test_all_requests_are_bounded_reads(self):
        opener = mock.Mock()
        for method, path, root in inspector.READS:
            opener.open.return_value = response({})
            inspector.read_config(opener, "https://192.168.1.50:7345", SECRET, method, path, root)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header("Auth"), SECRET)
            if method == "GET":
                self.assertEqual(path, "/app/current")
                self.assertIsNone(request.data)
            else:
                self.assertEqual(path, "/app/config/get_property")
                self.assertEqual(json.loads(request.data), {"VALUE": root})
        self.assertEqual(opener.open.call_count, 4)

    def test_writes_and_arbitrary_queries_are_rejected_before_network(self):
        opener = mock.Mock()
        for method, path, root in [
            ("PUT", "/app/store/set", "SmartCastHome"),
            ("PUT", "/app/launch", None),
            ("PUT", "/app/config/get_property", "Account"),
            ("GET", "/system/reboot", None),
        ]:
            with self.assertRaises(ValueError):
                inspector.read_config(opener, "https://192.168.1.50:7345", SECRET, method, path, root)
        opener.open.assert_not_called()

    def test_summaries_withhold_raw_values_credentials_and_identifiers(self):
        data = {"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "Dsk": SECRET, "Sns": SECRET, "SERIAL_NUMBER": SECRET,
            "AppInfo": {"NAME_SPACE": 4, "APP_ID": "1", "MESSAGE": json.dumps({
                "app": "home", "bundle": "bundles/home", "AUTH": SECRET, "token": SECRET
            })},
            "Home": {"URL": "https://example.invalid/?token=" + SECRET},
        }}}
        summary = inspector.summarize(data, "SmartCastHome")
        output = json.dumps(summary)
        self.assertNotIn(SECRET, output)
        self.assertNotIn("example.invalid", output)
        self.assertEqual(summary["home_app"]["bundle"], "bundles/home")
        self.assertEqual(summary["home_app"]["NAME_SPACE"], 4)

    def test_url_messages_are_not_printed(self):
        summary = inspector.app_summary({"NAME_SPACE": 4, "APP_ID": "17", "MESSAGE": "https://example.invalid/" + SECRET})
        self.assertEqual(summary["message_kind"], "URL (value withheld)")
        self.assertNotIn(SECRET, json.dumps(summary))

    def test_errors_never_echo_response_or_exception_details(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.URLError(SECRET)
        summary = inspector.read_config(opener, "https://192.168.1.50:7345", SECRET, *inspector.READS[0])
        self.assertNotIn(SECRET, json.dumps(summary))
        data = {"STATUS": {"RESULT": SECRET, "DETAIL": SECRET}}
        self.assertNotIn(SECRET, json.dumps(inspector.summarize(data, None)))

    def test_main_uses_no_proxy_or_redirect_and_redacts_reflected_token_keys(self):
        opener = mock.Mock()
        opener.open.side_effect = [response({}), response({SECRET: "ignored"}), response({}), response([])]
        output = io.StringIO()
        with mock.patch.dict(inspector.os.environ, {"TV_IP": "192.168.1.50", "VIZIO_TOKEN": SECRET}, clear=True), \
             mock.patch.object(inspector.urllib.request, "build_opener", return_value=opener) as build, \
             contextlib.redirect_stdout(output):
            inspector.main([])
        self.assertNotIn(SECRET, output.getvalue())
        self.assertEqual(len(json.loads(output.getvalue())["reads"]), 4)
        handlers = build.call_args.args
        self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler) and h.proxies == {} for h in handlers))
        redirect = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid/"))

    def test_noninteractive_token_prompt_is_rejected(self):
        with mock.patch.dict(inspector.os.environ, {"TV_IP": "192.168.1.50"}, clear=True), \
             mock.patch.object(inspector.sys.stdin, "isatty", return_value=False), \
             mock.patch.object(inspector.getpass, "getpass") as prompt:
            with self.assertRaisesRegex(SystemExit, "interactive Terminal"):
                inspector.main([])
            prompt.assert_not_called()

    def test_public_ip_is_rejected_before_network(self):
        with mock.patch.dict(inspector.os.environ, {"TV_IP": "8.8.8.8", "VIZIO_TOKEN": SECRET}, clear=True), \
             mock.patch.object(inspector.urllib.request, "build_opener") as build:
            with self.assertRaisesRegex(SystemExit, "private LAN"):
                inspector.main([])
            build.assert_not_called()

    def test_targeted_sections_include_static_assets_without_secrets(self):
        data = {"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "VIZIOHome": {"Assets": {"MainURL": "https://assets.vizio.com/ui/home.js?token=" + SECRET + "#" + SECRET},
                          "Auth": {"URL": "https://assets.vizio.com/" + SECRET + ".json"},
                          "UnknownString": SECRET},
            "SystemUI": {"Entry": "http://127.0.0.1:12345/scfs/ui/main.html?session=" + SECRET},
            "OtherConfig": {"URL": "https://assets.vizio.com/not-selected.js"},
        }}}
        summary = inspector.summarize(data, "AppConfigs")
        output = json.dumps(summary)
        self.assertNotIn(SECRET, output)
        self.assertIn("https://assets.vizio.com/ui/home.js", output)
        self.assertIn("http://127.0.0.1:12345/scfs/ui/main.html", output)
        self.assertNotIn("not-selected.js", output)
        self.assertIn("VIZIOHome:UnknownString", output)

    def test_asset_locations_reject_credentials_and_arbitrary_hosts_or_text(self):
        for value in ["https://user:password@assets.vizio.com/main.js", "https://" + SECRET + ".example.com/main.js",
                      "javascript:alert(1)", "http://[broken", SECRET]:
            self.assertEqual(inspector.asset_location(value), {})
        self.assertEqual(inspector.asset_location("https://assets.vizio.com/api/" + SECRET + "?token=" + SECRET),
                         {"source_origin": "https://assets.vizio.com"})

    def test_structure_is_bounded_and_withholds_arbitrary_values(self):
        tree = {"Section" + str(i): {"Field" + str(j): SECRET for j in range(60)} for i in range(60)}
        fields = inspector.section_structure(tree)
        self.assertLessEqual(len(fields), 100)
        self.assertNotIn(SECRET, json.dumps(fields))

    def test_report_preserves_descriptor_mismatch_without_conflating_homekit(self):
        current = inspector.summarize({"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "NAME_SPACE": 4, "APP_ID": "1", "MESSAGE": '{"app":"home","bundle":"bundles/home"}'}}}, None)
        configured = inspector.summarize({"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "AppInfo": {"NAME_SPACE": 2, "APP_ID": "1"}, "AppleConfig": {"HomeKitEnabled": True}}}}, "SmartCastHome")
        self.assertEqual(current["current_app"]["NAME_SPACE"], 4)
        self.assertEqual(configured["home_app"]["NAME_SPACE"], 2)
        self.assertEqual(configured["candidate_fields"], [])

    def test_app_cnames_and_escaped_or_encoded_token_redaction(self):
        summary = inspector.summarize({"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": [
            {"CNAME": "home", "APP_INFO": {"NAME_SPACE": 4, "APP_ID": "1"}}]}}, "VIZIOApps")
        self.assertEqual(summary["entries"][0]["CNAME"], "home")
        token = 'FAKE-"token/private'
        report = {token: {"asset_url": "https://assets.vizio.com/" + inspector.urllib.parse.quote(token, safe="") + ".js"}}
        output = json.dumps(inspector.redact_report(report, token))
        self.assertNotIn(inspector.urllib.parse.quote(token, safe=""), output)
        self.assertNotIn('FAKE-', output)

    def test_framework_mode_queries_only_the_three_reviewed_reads(self):
        opener = mock.Mock()
        opener.open.side_effect = [response({}), response({}), response({"ChromiumSettings": {"DebugEnabled": False}})]
        output = io.StringIO()
        with mock.patch.dict(inspector.os.environ, {"TV_IP": "192.168.1.50", "VIZIO_TOKEN": SECRET}, clear=True), \
             mock.patch.object(inspector.urllib.request, "build_opener", return_value=opener), \
             contextlib.redirect_stdout(output):
            inspector.main(["--framework"])
        report = json.loads(output.getvalue())
        self.assertEqual(report["inspector_version"], 3)
        self.assertEqual(report["inspection_mode"], "framework")
        self.assertEqual([r["root"] for r in report["reads"]], [None, "SmartCastHome", "ApplicationFramework"])
        self.assertEqual(opener.open.call_count, 3)
        self.assertEqual([json.loads(call.args[0].data)["VALUE"] for call in opener.open.call_args_list[1:]],
                         ["SmartCastHome", "ApplicationFramework"])

    def test_framework_structure_retains_only_safe_app_identity_and_bundle_paths(self):
        data = {"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "Applications": {"Home": {"NAME_SPACE": 4, "APP_ID": "1", "MESSAGE": '{"bundle":"bundles/home","token":"PRIVATE"}'},
                             "Other": {"Bundle": "bundles/other"}},
            "Auth": {"App": {"NAME_SPACE": 4, "APP_ID": "123", "MESSAGE": SECRET}},
            "OtherValue": SECRET,
        }}}
        summary = inspector.summarize(data, "ApplicationFramework")
        output = json.dumps(summary)
        self.assertIn('bundles/home', output)
        self.assertIn('bundles/other', output)
        self.assertNotIn(SECRET, output)
        self.assertNotIn('PRIVATE', output)
        self.assertNotIn('"123"', output)
        self.assertLessEqual(len(summary["selected_structure"]), 200)

    def test_asset_base_is_exposed_only_for_the_reviewed_vendor_field_without_query_or_credentials(self):
        data = {"STATUS": {"RESULT": "SUCCESS"}, "ITEM": {"VALUE": {
            "LocalAssetsUri": "https://scfs2.vizio.com/release/build123/?token=" + SECRET + "#" + SECRET,
            "ServiceMessageRouterUrl": "https://message-router.vizio.com/" + SECRET,
        }}}
        summary = inspector.summarize(data, "SmartCastHome")
        bases = [field["source_base"] for field in summary["selected_structure"] if "source_base" in field]
        self.assertEqual(bases, ["https://scfs2.vizio.com/release/build123/"])
        self.assertNotIn(SECRET, json.dumps(summary))
        self.assertEqual(inspector.asset_location("https://user:password@scfs2.vizio.com/private/", allow_base=True), {})


if __name__ == "__main__":
    unittest.main()
