import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from tracker.apple_client import AppleFeedClient, FeedError
from tracker.config import AppConfig
from tracker.models import FeedSection
from tracker.tracker import Top100Tracker


ROOT = Path(__file__).resolve().parents[1]


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


def legacy_entry(app_id="123"):
    return {"id": {"label": f"https://apps.apple.com/us/app/example/id{app_id}"},
            "im:name": {"label": "Example"}}


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.client = AppleFeedClient("us")
        self.addCleanup(self.client.session.close)

    def test_overall_falls_back_to_legacy_on_request_failure(self):
        with patch.object(self.client.session, "get", side_effect=[
            requests.Timeout("unavailable"), response({"feed": {"entry": [legacy_entry()]}})
        ]) as get:
            section = self.client.fetch_section("top-free", "all")
        self.assertEqual(section.ranks, {"123": 1})
        self.assertEqual(get.call_args.args[0],
                         "https://itunes.apple.com/us/rss/topfreeapplications/limit=100/json")

    def test_empty_overall_response_uses_fallback(self):
        with patch.object(self.client.session, "get", side_effect=[
            response({"feed": {"results": []}}),
            response({"feed": {"entry": [legacy_entry()]}}),
        ]):
            self.assertEqual(len(self.client.fetch_section("top-paid", "all").items), 1)

    def test_category_does_not_fall_back_to_overall(self):
        with patch.object(self.client.session, "get", side_effect=requests.Timeout()) as get:
            with self.assertRaisesRegex(FeedError, "top-free:6018"):
                self.client.fetch_section("top-free", "6018")
        self.assertEqual(get.call_count, 1)

    def test_short_legacy_chart_and_single_entry_are_valid(self):
        for entries in ([legacy_entry()], legacy_entry()):
            with self.subTest(entries=entries), patch.object(
                self.client.session, "get", return_value=response({"feed": {"entry": entries}})
            ):
                section = self.client.fetch_section("top-paid", "6021")
                self.assertEqual(section.ranks, {"123": 1})

    def test_invalid_payloads_fail_instead_of_reporting_zero_apps(self):
        for payload in ({}, [], {"feed": {"entry": []}}, {"feed": {"entry": [None]}},
                        {"feed": {"entry": [{"im:name": {"label": "No ID"}}]}},
                        {"feed": {"entry": [legacy_entry(), legacy_entry()]}}):
            with self.subTest(payload=payload), patch.object(
                self.client.session, "get", return_value=response(payload)
            ):
                with self.assertRaises(FeedError):
                    self.client.fetch_section("top-free", "6018")

    def test_overall_preserves_rank_order(self):
        with patch.object(self.client.session, "get", return_value=response({"feed": {
            "results": [{"id": "20", "name": "Second ID"}, {"id": "10", "name": "First ID"}]
        }})):
            section = self.client.fetch_section("top-free", "all")
        self.assertEqual(section.ranks, {"20": 1, "10": 2})

    def test_transient_http_failure_is_retried(self):
        class Handler(BaseHTTPRequestHandler):
            calls = 0

            def do_GET(self):
                Handler.calls += 1
                self.send_response(503 if Handler.calls == 1 else 200)
                self.end_headers()
                self.wfile.write(b'{"feed":{"results":[{"id":"123"}]}}')

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.client.session.mount("http://", self.client.session.get_adapter("https://"))
            rows = self.client._fetch_rows(f"http://127.0.0.1:{server.server_port}/", "results")
            self.assertEqual(rows[0]["id"], "123")
            self.assertEqual(Handler.calls, 2)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_failed_snapshot_preserves_history_and_does_not_notify(self):
        cfg = AppConfig.load(ROOT / "config.yaml")
        cfg.feeds = [{"type": "top-free", "genres": ["all", "6018"]}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracker = Top100Tracker(cfg, root, templates_dir=str(ROOT / "templates"))
            self.addCleanup(tracker.client.session.close)
            seen = root / "docs/history/seen_global.json"
            seen.write_text('["42"]')
            with patch.object(tracker.client, "fetch_section", side_effect=[
                FeedSection("top-free:all", "top-free", "all", [], {}), FeedError("unavailable")
            ]), patch.object(tracker, "notify") as notify:
                with self.assertRaises(FeedError):
                    tracker.run_once()
            self.assertEqual(seen.read_text(), '["42"]')
            self.assertEqual(list((root / "docs/history").iterdir()), [seen])
            notify.assert_not_called()

    def test_diagnostic_checks_remaining_feeds_after_failure(self):
        from tracker.main import main
        cfg = AppConfig.load(ROOT / "config.yaml")
        cfg.feeds = [{"type": "top-free", "genres": ["all", "6018"]}]
        with patch("sys.argv", ["tracker.main", "--check-feeds"]), \
             patch("tracker.main.AppConfig.load", return_value=cfg), \
             patch("tracker.main.AppleFeedClient") as client, \
             patch("tracker.main.Top100Tracker") as tracker, patch("builtins.print"):
            client.return_value.fetch_section.side_effect = [
                FeedError("unavailable"), FeedSection("top-free:6018", "top-free", "6018", [], {})
            ]
            self.assertEqual(main(), 1)
            self.assertEqual(client.return_value.fetch_section.call_count, 2)
            tracker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
