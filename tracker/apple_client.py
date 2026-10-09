# tracker/apple_client.py
import logging
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List
from .models import AppItem, FeedSection

V1_FEED_PATH = {
    "top-free": "topfreeapplications",
    "top-paid": "toppaidapplications",
    "top-grossing": "topgrossingapplications",
}

logger = logging.getLogger(__name__)


class FeedError(RuntimeError):
    """A chart could not be fetched or contained unusable data."""


class AppleFeedClient:
    def __init__(self, country: str, timeout: int = 30):
        self.country = country
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _v2_overall_url(self, feed_type: str) -> str:
        # v2 overall (no genre support)
        return f"https://rss.marketingtools.apple.com/api/v2/{self.country}/apps/{feed_type}/100/apps.json"

    def _v1_genre_url(self, feed_type: str, genre: str) -> str:
        # v1 legacy with genre support
        path = V1_FEED_PATH[feed_type]
        genre_path = "" if genre == "all" else f"/genre={genre}"
        return f"https://itunes.apple.com/{self.country}/rss/{path}/limit=100{genre_path}/json"

    def _fetch_rows(self, url: str, field: str) -> List[dict]:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        feed = data.get("feed") if isinstance(data, dict) else None
        rows = feed.get(field) if isinstance(feed, dict) else None
        # Legacy feeds can encode a single entry as an object.
        if field == "entry" and isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            raise FeedError(f"Missing, empty, or invalid {field} in {url}")
        return rows

    def _validate(self, section: FeedSection) -> FeedSection:
        ids = [item.id for item in section.items]
        if not ids or any(not app_id for app_id in ids) or len(set(ids)) != len(ids):
            raise FeedError(f"Invalid or duplicate app IDs in {section.key}")
        return section

    def _v1_extract_href(self, link_obj) -> str:
        """Return the first usable href/label from the v1 'link' field (dict OR list)."""
        if not link_obj:
            return ""
        # dict shape
        if isinstance(link_obj, dict):
            return (link_obj.get("attributes", {}) or {}).get("href") or link_obj.get("label", "") or ""
        # list shape
        if isinstance(link_obj, list):
            # prefer attributes.href if present
            for l in link_obj:
                if isinstance(l, dict):
                    href = (l.get("attributes", {}) or {}).get("href")
                    if href:
                        return href
            # fallback to any label
            for l in link_obj:
                if isinstance(l, dict) and l.get("label"):
                    return l["label"]
        return ""

    def _v1_extract_app_id(self, entry: dict) -> str:
        """Prefer id.attributes['im:id']; fallback to digits in id.label (/id123456...)."""
        id_obj = entry.get("id") or {}
        attrs = id_obj.get("attributes") or {}
        app_id = attrs.get("im:id")
        if app_id:
            return app_id
        label = id_obj.get("label") or ""
        m = re.search(r"/id(\d+)", label) or re.search(r"\bid=(\d+)\b", label)
        return m.group(1) if m else ""

    def _v1_extract_name(self, entry: dict) -> str:
        return (entry.get("im:name") or {}).get("label") \
            or (entry.get("title") or {}).get("label") \
            or ""

    def _v1_extract_artist(self, entry: dict) -> str:
        return (entry.get("im:artist") or {}).get("label") \
            or (entry.get("artist") or {}).get("label") \
            or ""

    def _v1_extract_artwork(self, entry: dict) -> str:
        # pick the largest image by 'attributes.height' if present, else last one
        imgs = entry.get("im:image") or []
        best = ""
        best_h = -1
        for img in imgs:
            h = -1
            attrs = img.get("attributes") or {}
            try:
                h = int(attrs.get("height", -1))
            except Exception:
                pass
            if h > best_h:
                best_h = h
                best = img.get("label") or best
        if best:
            return best
        # fallback: some feeds store artwork in 'im:image' missing; rarely, use id.label (not ideal)
        return (entry.get("id") or {}).get("label") or ""

    def fetch_section(self, feed_type: str, genre: str) -> FeedSection:
        genre = str(genre)
        if feed_type not in V1_FEED_PATH:
            raise FeedError(f"Unsupported feed type: {feed_type}")
        try:
            if genre == "all" and feed_type != "top-grossing":
                try:
                    return self._fetch_v2(feed_type, genre)
                except (requests.RequestException, ValueError, FeedError) as exc:
                    logger.warning("%s:%s v2 failed; trying legacy overall feed: %s", feed_type, genre, exc)
            return self._fetch_v1(feed_type, genre)
        except (requests.RequestException, ValueError, FeedError) as exc:
            raise FeedError(f"Could not load {feed_type}:{genre}: {exc}") from exc

    def _fetch_v2(self, feed_type: str, genre: str) -> FeedSection:
        # --- v2 overall ---
        url = self._v2_overall_url(feed_type)
        results = self._fetch_rows(url, "results")

        items: List[AppItem] = []
        ranks: Dict[str, int] = {}
        for rank, raw in enumerate(results, start=1):
            app_id = str(raw.get("id") or "")
            items.append(AppItem(
                id=app_id,
                name=raw.get("name"),
                artist=raw.get("artistName"),
                url=raw.get("url"),
                artwork=raw.get("artworkUrl100"),
                release_date=raw.get("releaseDate") or "",
            ))
            ranks[app_id] = rank
        return self._validate(FeedSection(
            key=f"{feed_type}:{genre}", feed_type=feed_type, genre=genre,
            items=items, ranks=ranks
        ))

    def _fetch_v1(self, feed_type: str, genre: str) -> FeedSection:
        # now use the helpers:
        url = self._v1_genre_url(feed_type, str(genre))
        entries = self._fetch_rows(url, "entry")

        items: List[AppItem] = []
        ranks: Dict[str, int] = {}

        for rank, e in enumerate(entries, start=1):
            app_id = str(self._v1_extract_app_id(e))
            if not app_id:
                raise FeedError(f"Missing app ID in {feed_type}:{genre} at rank {rank}")
            name = self._v1_extract_name(e)
            artist = self._v1_extract_artist(e)
            link = self._v1_extract_href(e.get("link"))
            artwork = self._v1_extract_artwork(e)

            items.append(AppItem(id=app_id, name=name,
                         artist=artist, url=link, artwork=artwork,
                         release_date=(e.get("im:releaseDate") or {}).get("label", "")))
            ranks[app_id] = rank

        return self._validate(FeedSection(
            key=f"{feed_type}:{genre}", feed_type=feed_type, genre=str(genre),
            items=items, ranks=ranks
        ))
