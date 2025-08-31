# tracker/apple_client.py
import requests
from typing import Dict, List
from .models import AppItem, FeedSection

V1_FEED_PATH = {
    "top-free": "topfreeapplications",
    "top-paid": "toppaidapplications",
    "top-grossing": "topgrossingapplications",
}


class AppleFeedClient:
    def __init__(self, country: str, timeout: int = 30):
        self.country = country
        self.timeout = timeout

    def _v2_overall_url(self, feed_type: str) -> str:
        # v2 overall (no genre support)
        return f"https://rss.applemarketingtools.com/api/v2/{self.country}/apps/{feed_type}/100/apps.json"

    def _v1_genre_url(self, feed_type: str, genre: str) -> str:
        # v1 legacy with genre support
        path = V1_FEED_PATH[feed_type]
        return f"https://itunes.apple.com/{self.country}/rss/{path}/limit=100/genre={genre}/json"

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
        if genre == "all":
            # --- v2 overall ---
            url = self._v2_overall_url(feed_type)
            r = requests.get(url, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            results = data.get("feed", {}).get("results", []) or []

            items: List[AppItem] = []
            ranks: Dict[str, int] = {}
            for rank, raw in enumerate(results, start=1):
                app_id = raw.get("id")
                items.append(AppItem(
                    id=app_id,
                    name=raw.get("name"),
                    artist=raw.get("artistName"),
                    url=raw.get("url"),
                    artwork=raw.get("artworkUrl100"),
                ))
                ranks[app_id] = rank
            return FeedSection(
                key=f"{feed_type}:{genre}", feed_type=feed_type, genre=genre,
                items=items, ranks=ranks
            )

        # now use the helpers:
        url = self._v1_genre_url(feed_type, str(genre))
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        entries = data.get("feed", {}).get("entry", []) or []

        items: List[AppItem] = []
        ranks: Dict[str, int] = {}

        for rank, e in enumerate(entries, start=1):
            app_id = self._v1_extract_app_id(e)
            if not app_id:
                continue  # skip weird rows with no ID
            name = self._v1_extract_name(e)
            artist = self._v1_extract_artist(e)
            link = self._v1_extract_href(e.get("link"))
            artwork = self._v1_extract_artwork(e)

            items.append(AppItem(id=app_id, name=name,
                         artist=artist, url=link, artwork=artwork))
            ranks[app_id] = rank

        return FeedSection(
            key=f"{feed_type}:{genre}", feed_type=feed_type, genre=str(genre),
            items=items, ranks=ranks
        )
