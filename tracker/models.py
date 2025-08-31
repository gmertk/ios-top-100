from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AppItem:
    id: str
    name: str
    artist: str
    url: str
    artwork: str


@dataclass
class FeedSection:
    key: str            # e.g., "top-free:6014"
    feed_type: str      # top-free, top-paid, top-grossing
    genre: str          # "all" or numeric string
    items: List[AppItem]
    ranks: Dict[str, int]  # app_id -> rank


@dataclass
class Snapshot:
    date: str
    country: str
    feeds: Dict[str, FeedSection]  # key -> section


@dataclass
class SectionReport:
    feed_label: str
    genre_label: str
    count: int
    apps: List[dict]  # simplified dicts for rendering


@dataclass
class DailyReport:
    date: str
    country: str
    total_new: int
    sections: List[SectionReport]
