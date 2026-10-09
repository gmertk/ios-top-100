import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tracker.config import AppConfig
from tracker.insights import build_insights
from tracker.models import AppItem, FeedSection, Snapshot
from tracker.models import DailyReport
from tracker.renderers import SiteRenderer
from tracker.stores import SnapshotStore
from tracker.tracker import Top100Tracker

ROOT = Path(__file__).resolve().parents[1]


def snapshot(day="2026-10-09", rank=20, app_id="a", genre="6018", release="2026-09-01"):
    key = f"top-free:{genre}"
    app = AppItem(app_id, "Example", "Maker", "https://example.com", "", release)
    return Snapshot(day, "us", {key: FeedSection(key, "top-free", genre, [app], {app_id: rank})})


def history(day, rank=50, app_id="a", key="top-free:6018", country="us"):
    return {"date": day, "country": country, "feeds": {key: {"ranks": {app_id: rank}}}}


def window(result, days):
    return next(w for w in result["windows"] if w["days"] == days)


class InsightTests(unittest.TestCase):
    def test_existing_app_can_be_shortlisted_with_exact_rank_evidence(self):
        result = build_insights(snapshot(), [history("2026-10-02", 80)], {})
        candidate = window(result, 7)["shortlist"][0]
        self.assertEqual(result["new_ids"], [])
        self.assertEqual(candidate["signal"]["gain"], 60)
        self.assertEqual(candidate["signal"]["observed_days"], 2)
        self.assertEqual(candidate["signal"]["streak"], 0)
        self.assertEqual(candidate["signal"]["observations"][1]["rank"], None)

    def test_gap_is_not_substituted_for_weekly_baseline(self):
        result = build_insights(snapshot(), [history("2025-11-12", 90), history("2026-10-01", 80)], {})
        self.assertFalse(window(result, 7)["available"])
        self.assertEqual(window(result, 7)["shortlist"], [])
        self.assertEqual(result["gap_days"], 8)

    def test_no_comparison_across_countries_or_categories(self):
        result = build_insights(snapshot(), [history("2026-10-02", 80, country="gb")], {})
        self.assertFalse(window(result, 7)["available"])
        result = build_insights(snapshot(), [history("2026-10-02", 80, key="top-free:6000")], {})
        self.assertFalse(window(result, 7)["available"])

    def test_absent_app_never_gets_invented_rank(self):
        result = build_insights(snapshot(), [history("2026-10-02", 80, app_id="other")], {})
        self.assertTrue(window(result, 7)["available"])
        self.assertEqual(window(result, 7)["total_movers"], 0)
        self.assertEqual(result["new_ids"], ["a"])

    def test_unique_new_apps_and_strongest_chart_per_mover(self):
        snap = snapshot()
        snap.feeds.update(snapshot(genre="6000", rank=10).feeds)
        baseline = history("2026-10-02", 80)
        baseline["feeds"].update(history("2026-10-02", 90, key="top-free:6000")["feeds"])
        result = build_insights(snap, [baseline], {})
        candidates = window(result, 7)["shortlist"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["signal"]["gain"], 80)
        self.assertEqual(candidates[0]["rising_charts"], 2)
        result = build_insights(snap, [history("2026-10-02", app_id="other")], {})
        self.assertEqual(result["total_apps"], 1)
        self.assertEqual(result["new_ids"], ["a"])
        self.assertEqual(len(result["discoveries"]), 1)

    def test_streak_requires_consecutive_daily_improvement(self):
        result = build_insights(snapshot(), [history("2026-10-06", 50), history("2026-10-07", 40),
                                             history("2026-10-08", 30)], {})
        self.assertEqual(window(result, 3)["shortlist"][0]["signal"]["streak"], 3)
        result = build_insights(snapshot(), [history("2026-10-06", 50), history("2026-10-08", 30)], {})
        self.assertEqual(window(result, 3)["shortlist"][0]["signal"]["streak"], 1)

    def test_legacy_ids_preserve_rank_order_and_declines_are_excluded(self):
        baseline = {"date": "2026-10-08", "country": "us",
                    "feeds": {"top-free:6018": {"ids": ["other", "a"]}}}
        result = build_insights(snapshot(rank=1), [baseline], {})
        self.assertEqual(window(result, 1)["shortlist"][0]["signal"]["gain"], 1)
        result = build_insights(snapshot(rank=3), [baseline], {})
        self.assertEqual(window(result, 1)["shortlist"], [])

    def test_release_age_is_separate_from_first_observed_date(self):
        for release in ("2020-01-01", "", "not-a-date", "2027-01-01"):
            with self.subTest(release=release):
                result = build_insights(snapshot(release=release), [history("2026-10-08", app_id="other")], {})
                self.assertEqual(result["new_ids"], ["a"])
                self.assertEqual(result["discoveries"], [])
        result = build_insights(snapshot(), [history("2026-10-08", app_id="other")], {})
        self.assertEqual(result["discoveries"][0]["age_days"], 38)

    def test_first_snapshot_establishes_baseline(self):
        result = build_insights(snapshot(), [], {})
        self.assertTrue(result["baseline"])
        self.assertEqual(result["new_ids"], [])

    def test_shortlist_limits_and_ranking_are_deterministic(self):
        snap = snapshot()
        section = snap.feeds["top-free:6018"]
        section.items = [AppItem(str(i), f"App {i}", "Maker", "", "") for i in range(8)]
        section.ranks = {str(i): i + 1 for i in range(8)}
        baseline = history("2026-10-02")
        baseline["feeds"]["top-free:6018"]["ranks"] = {str(i): (i + 1) * 10 for i in range(8)}
        result = window(build_insights(snap, [baseline], {}), 7)
        self.assertEqual([a["id"] for a in result["shortlist"]], ["7", "6", "5", "4", "3"])
        self.assertEqual(len(result["movers"]), 3)
        self.assertEqual(result["total_movers"], 8)

    def test_populated_momentum_renders_evidence_and_gap_in_timeline(self):
        insights = build_insights(snapshot(), [history("2026-10-02", 80)], {})
        report = DailyReport("2026-10-09", "us", 0, [], insights)
        with tempfile.TemporaryDirectory() as tmp:
            SiteRenderer(ROOT / "templates", Path(tmp), "App Radar", "").render_report(report)
            html = (Path(tmp) / "2026-10-09.html").read_text()
        self.assertIn('↑ 60 places', html)
        self.assertIn('#80 → #20', html)
        self.assertIn('2/8 daily observations', html)
        self.assertIn('2026-10-03: No observation', html)
        self.assertIn('<circle', html)

    def test_history_excludes_today_future_metadata_and_other_storefronts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SnapshotStore(Path(tmp))
            store.save_snapshot(snapshot(day="2026-10-08"))
            store.save_snapshot(snapshot())
            store.save_snapshot(snapshot(day="2026-10-10"))
            (Path(tmp) / "2026-10-08.meta.json").write_text('{"total_new":1}')
            (Path(tmp) / "seen_global.json").write_text('["a"]')
            rows = store.history_before("2026-10-09", "us")
            self.assertEqual([r["date"] for r in rows], ["2026-10-08"])
            self.assertEqual(rows[0]["feeds"]["top-free:6018"]["ranks"], {"a": 20})
            self.assertEqual(rows[0]["feeds"]["top-free:6018"]["items"][0]["release_date"], "2026-09-01")
            self.assertEqual(store.history_before("2026-10-09", "gb"), [])

    def test_run_is_repeatable_with_unique_totals_and_escaped_html(self):
        cfg = AppConfig.load(ROOT / "config.yaml")
        cfg.telegram.enabled = False
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracker = Top100Tracker(cfg, root, templates_dir=str(ROOT / "templates"))
            self.addCleanup(tracker.client.session.close)
            tracker.snapshots.save_snapshot(snapshot(day="2026-10-08", app_id="old"))
            snap = snapshot(app_id="new")
            snap.feeds.update(snapshot(app_id="new", genre="6000").feeds)
            item = snap.feeds["top-free:6018"].items[0]
            snap.feeds["top-free:6018"].items[0] = AppItem(item.id, '<script>alert("x")</script>',
                                                          item.artist, item.url, item.artwork, item.release_date)
            with patch.object(tracker, "fetch_snapshot", return_value=snap):
                tracker.run_once()
                tracker.run_once()
            report = tracker.build_report(snap)
            self.assertEqual(report.total_new, 1)
            self.assertEqual(sum(s.count for s in report.sections), 2)
            html = (root / "docs/2026-10-09.html").read_text()
            self.assertIn('&lt;script&gt;', html)
            self.assertNotIn('<script>alert', html)
            self.assertIn('No 7-day comparison yet', html)
            self.assertIn('href="./index.html"', html)
            self.assertEqual(json.loads((root / "docs/history/2026-10-09.meta.json").read_text())["total_new"], 1)


if __name__ == "__main__":
    unittest.main()
