"""Launch-helper checks; all TV I/O is mocked."""

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
    "launcher", Path(__file__).resolve().parents[1] / "scripts" / "launch-quietframe.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
SECRET = "FAKE-external-test-token"


class LauncherTests(unittest.TestCase):
    def run_launch(self, *, host="192.168.1.50", url="https://example.github.io/quietframe/", result=None, error=None):
        output = io.StringIO()
        opener = mock.Mock()
        opener.open.return_value = io.BytesIO(json.dumps(result or {"STATUS": {"RESULT": "SUCCESS"}}).encode())
        if error:
            opener.open.side_effect = error
        with mock.patch.dict(launcher.os.environ, {}, clear=True), \
             mock.patch("builtins.input", side_effect=[host, url]), \
             mock.patch.object(launcher.getpass, "getpass", return_value=SECRET), \
             mock.patch.object(launcher.urllib.request, "build_opener", return_value=opener) as build, \
             contextlib.redirect_stdout(output):
            try:
                launcher.main()
            except SystemExit as exc:
                output.write(str(exc))
        self.assertNotIn(SECRET, output.getvalue())
        return output.getvalue(), opener, build

    def test_single_verified_launch_payload_and_no_proxy_or_redirects(self):
        output, opener, build = self.run_launch()
        self.assertIn("Launch accepted", output)
        opener.open.assert_called_once()
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://192.168.1.50:7345/app/launch")
        self.assertEqual(request.method, "PUT")
        self.assertEqual(request.get_header("Auth"), SECRET)
        self.assertEqual(json.loads(request.data), {"VALUE": {
            "MESSAGE": "https://example.github.io/quietframe/", "NAME_SPACE": 4, "APP_ID": "17"
        }})
        handlers = build.call_args.args
        self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler) and h.proxies == {} for h in handlers))
        redirect = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        self.assertIsNone(redirect.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.invalid"))

    def test_rejects_non_tv_addresses_before_sending(self):
        for host in ["example.com", "8.8.8.8", "127.0.0.1", "0.0.0.0", "224.0.0.1"]:
            with self.subTest(host=host):
                _, opener, _ = self.run_launch(host=host)
                opener.open.assert_not_called()

    def test_rejects_http_and_embedded_credentials(self):
        for url in ["http://example.github.io/", "https://user:pass@example.com/", "https://"]:
            with self.subTest(url=url):
                _, opener, _ = self.run_launch(url=url)
                opener.open.assert_not_called()

    def test_does_not_echo_response_or_exception_secrets(self):
        for result in [{"STATUS": {"RESULT": SECRET, "DETAIL": SECRET}}, [SECRET]]:
            output, _, _ = self.run_launch(result=result)
            self.assertIn("did not report SUCCESS", output)
        output, _, _ = self.run_launch(error=urllib.error.URLError(SECRET))
        self.assertIn("Check the TV before retrying", output)


if __name__ == "__main__":
    unittest.main()
