import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Iterable, Set
from .models import Snapshot, FeedSection


class SnapshotStore:
    """Persists daily snapshots for reproducibility and diffs (if needed)."""

    def __init__(self, history_dir: Path):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, snap: Snapshot) -> None:
        path = self.history_dir / f"{snap.date}.json"
        data = {
            "date": snap.date,
            "country": snap.country,
            "feeds": {
                k: {
                    "feed_type": s.feed_type,
                    "genre": s.genre,
                    "ids": [i.id for i in s.items],
                    "ranks": s.ranks,
                    "items": [asdict(i) for i in s.items],
                } for k, s in snap.feeds.items()
            }
        }
        path.write_text(json.dumps(data, ensure_ascii=False,
                        indent=2), encoding="utf-8")
        # Update latest pointer
        (self.history_dir / "latest.json").write_text(json.dumps(data,
                                                                 ensure_ascii=False, indent=2), encoding="utf-8")

    def list_report_dates(self) -> List[str]:
        dates = []
        for path in self.history_dir.glob("*.json"):
            try:
                date.fromisoformat(path.stem)
            except ValueError:
                continue
            dates.append(path.stem)
        return sorted(dates)

    def history_before(self, before: str, country: str) -> List[dict]:
        history = []
        for day in self.list_report_dates():
            if day >= before:
                continue
            data = json.loads((self.history_dir / f"{day}.json").read_text(encoding="utf-8"))
            if data.get("country") == country and data.get("date") == day:
                history.append(data)
        return history


class MetaStore:
    """Stores small metadata (e.g., totals per day)."""

    def __init__(self, history_dir: Path):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_total_new(self, date: str, total: int) -> None:
        (self.history_dir / f"{date}.meta.json").write_text(
            json.dumps({"total_new": total}, indent=2), encoding="utf-8")

    def load_total_new(self, date: str) -> int:
        p = self.history_dir / f"{date}.meta.json"
        if not p.exists():
            return -1
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("total_new", -1)
        except Exception:
            return -1


class SeenStore:
    """Global 'first-ever' registry: once an app ID is seen, never report it again."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: Set[str] = self._load()

    def _load(self) -> Set[str]:
        if self.path.exists():
            try:
                return set(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                return set()
        return set()

    def mark_seen(self, app_ids: Iterable[str]) -> None:
        self._seen.update(app_ids)
        self.path.write_text(json.dumps(
            sorted(list(self._seen))), encoding="utf-8")

    def unseen_only(self, app_ids: Iterable[str]) -> List[str]:
        return [a for a in app_ids if a not in self._seen]
