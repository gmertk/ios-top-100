from dataclasses import dataclass
from typing import Dict, List, Any
import yaml
from pathlib import Path

DEFAULT_GENRE_LABELS = {
    "all": "Overall",
    "6014": "Games",
    "6007": "Productivity",
    "6017": "Education",
    "6008": "Photo & Video",
    "6013": "Health & Fitness",
    "6015": "Finance",
    "6011": "Music",
    "6005": "Social Networking",
}

FEED_LABELS = {
    "top-free": "Top Free",
    "top-paid": "Top Paid",
    "top-grossing": "Top Grossing",
}


@dataclass
class SiteConfig:
    title: str
    base_url: str


@dataclass
class TelegramConfig:
    enabled: bool
    chat_id: str


@dataclass
class AppConfig:
    country: str
    feeds: List[dict]
    genre_labels: Dict[str, str]
    site: SiteConfig
    telegram: TelegramConfig

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        genre_labels = {**DEFAULT_GENRE_LABELS, **
                        {str(k): v for k, v in (data.get("genre_labels") or {}).items()}}
        site = data.get("site", {})
        tg = data.get("telegram", {})
        return cls(
            country=data.get("country", "us"),
            feeds=data.get("feeds", []),
            genre_labels=genre_labels,
            site=SiteConfig(
                title=site.get(
                    "title", "Daily First-Ever Entrants — iOS Top 100"),
                base_url=site.get("base_url", "").rstrip("/"),
            ),
            telegram=TelegramConfig(
                enabled=bool(tg.get("enabled", False)),
                chat_id=str(tg.get("chat_id", "")),
            ),
        )
