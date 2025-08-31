from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

from .apple_client import AppleFeedClient
from .config import AppConfig, FEED_LABELS
from .models import Snapshot, FeedSection, SectionReport, DailyReport
from .stores import SnapshotStore, SeenStore, MetaStore
from .renderers import SiteRenderer
from .notifier import TelegramNotifier


class Top100Tracker:
    """
    Orchestrates fetching charts, computing first-ever entrants,
    rendering static HTML, and sending notifications.
    """

    def __init__(
        self,
        cfg: AppConfig,
        workspace: Path,      # repo root
        docs_subdir: str = "docs",
        history_subdir: str = "docs/history",
        templates_dir: str = "templates",
    ):
        self.cfg = cfg
        self.root = workspace
        self.docs_dir = self.root / docs_subdir
        self.history_dir = self.root / history_subdir
        self.templates_dir = self.root / templates_dir

        self.client = AppleFeedClient(cfg.country)
        self.snapshots = SnapshotStore(self.history_dir)
        self.seen = SeenStore(self.history_dir / "seen_global.json")
        self.meta = MetaStore(self.history_dir)
        self.renderer = SiteRenderer(
            templates_dir=self.templates_dir,
            docs_dir=self.docs_dir,
            site_title=cfg.site.title,
            base_url=cfg.site.base_url,
        )
        self.notifier = TelegramNotifier(
            cfg.telegram.enabled, cfg.telegram.chat_id)

    def _today_iso(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def fetch_snapshot(self) -> Snapshot:
        feeds: Dict[str, FeedSection] = {}
        for f in self.cfg.feeds:
            ftype = f["type"]
            for g in f["genres"]:
                genre = str(g)
                section = self.client.fetch_section(ftype, genre)
                feeds[section.key] = section
        return Snapshot(date=self._today_iso(), country=self.cfg.country, feeds=feeds)

    def build_report(self, snap: Snapshot) -> DailyReport:
        # Global first-ever logic
        total_new = 0
        sections: List[SectionReport] = []

        for key, sec in snap.feeds.items():
            new_ids = self.seen.unseen_only([i.id for i in sec.items])

            apps_out = []
            id_to_item = {i.id: i for i in sec.items}
            for app_id in new_ids:
                it = id_to_item[app_id]
                apps_out.append({
                    "id": it.id,
                    "name": it.name,
                    "artist": it.artist,
                    "url": it.url,
                    "artwork": it.artwork,
                    "rank": sec.ranks.get(app_id),
                })

            sections.append(
                SectionReport(
                    feed_label=FEED_LABELS.get(sec.feed_type, sec.feed_type),
                    genre_label=self.cfg.genre_labels.get(
                        sec.genre, sec.genre),
                    count=len(new_ids),
                    apps=apps_out,
                )
            )
            total_new += len(new_ids)

        # Sort sections by most new
        sections.sort(key=lambda s: s.count, reverse=True)

        return DailyReport(
            date=snap.date,
            country=snap.country,
            total_new=total_new,
            sections=sections,
        )

    def publish(self, report: DailyReport) -> None:
        # Render daily report
        self.renderer.render_report(report)

        # Build index from existing HTML files and metadata
        reports_for_index: List[Dict[str, str]] = []
        for p in sorted(self.docs_dir.glob("*.html")):
            if p.name == "index.html":
                continue
            date = p.stem
            total = self.meta.load_total_new(date)
            reports_for_index.append({
                "date": date,
                "href": p.name,
                "total_new": total if total >= 0 else "?",
            })
        # Sort newest first
        reports_for_index.sort(key=lambda r: r["date"], reverse=True)

        self.renderer.render_index(self.cfg.country, reports_for_index)

    def notify(self, report: DailyReport) -> None:
        if not self.cfg.site.base_url:
            return
        link = f"{self.cfg.site.base_url}/{report.date}.html"
        msg = f"📈 iOS Top 100 — {self.cfg.country.upper()} — {report.date}\nFirst-ever entrants today: {report.total_new}\n{link}"
        self.notifier.send(msg)

    def run_once(self) -> None:
        snap = self.fetch_snapshot()
        self.snapshots.save_snapshot(snap)
        report = self.build_report(snap)
        # Persist total for index
        self.meta.save_total_new(report.date, report.total_new)
        self.publish(report)

        # Mark everything seen today so re-entries never show again
        all_today_ids = []
        for sec in snap.feeds.values():
            all_today_ids.extend([i.id for i in sec.items])
        self.seen.mark_seen(all_today_ids)

        # Optional notify
        self.notify(report)
