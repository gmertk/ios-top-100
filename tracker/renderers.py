from dataclasses import asdict
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import List, Dict
from .models import DailyReport
from .config import FEED_LABELS


class SiteRenderer:
    """Renders the static site (daily report + index) using Jinja templates."""

    def __init__(self, templates_dir: Path, docs_dir: Path, site_title: str, base_url: str):
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.site_title = site_title
        self.base_url = base_url.rstrip("/")

    def render_report(self, report: DailyReport) -> None:
        tmpl = self.env.get_template("report.html.j2")
        html = tmpl.render(
            site_title=self.site_title,
            date=report.date,
            country=report.country,
            sections=[asdict(s) for s in report.sections],
            total_new=report.total_new,
            base_url=self.base_url,
            now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
        (self.docs_dir /
         f"{report.date}.html").write_text(html, encoding="utf-8")

    def render_index(self, country: str, reports: List[Dict[str, str]]) -> None:
        tmpl = self.env.get_template("index.html.j2")
        html = tmpl.render(
            site_title=self.site_title,
            reports=reports,
            country=country,
            now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
        (self.docs_dir / "index.html").write_text(html, encoding="utf-8")
