"""Explainable discovery signals, comparing ranks only within the same chart."""
from dataclasses import asdict
from datetime import date, timedelta

from .config import FEED_LABELS
from .models import Snapshot

WINDOWS = (1, 3, 7, 30)


def signal_order(signal):
    return (signal["streak"] < 3, -signal["gain"], -signal["streak"],
            signal["rank"], signal["key"])


def movement_pattern(observations, streak):
    if streak >= 3:
        return "Sustained climb"
    if len(observations) == 2:
        return "One-day rise"
    if any(rank is None for _, rank in observations):
        return "Limited history"
    gain = observations[0][1] - observations[-1][1]
    largest_daily_gain = max(older[1] - newer[1] for older, newer in zip(observations, observations[1:]))
    if largest_daily_gain >= gain * 0.7:
        return "Jump-led rise"
    return "Mixed movement"


def ranks_for(feed: dict) -> dict:
    # Historical snapshots stored IDs in rank order. New snapshots preserve
    # explicit ranks, including any gaps returned by a provider.
    if "ranks" in feed:
        return feed["ranks"]
    return {str(app_id): rank for rank, app_id in enumerate(feed.get("ids", []), 1)}


def build_insights(snap: Snapshot, history: list, genre_labels: dict) -> dict:
    today = date.fromisoformat(snap.date)
    history = sorted((h for h in history if h.get("country") == snap.country
                      and h["date"] < snap.date), key=lambda h: h["date"])
    by_date = {h["date"]: h for h in history}
    first_seen = {}
    for h in history:
        for feed in h["feeds"].values():
            for app_id in ranks_for(feed):
                first_seen.setdefault(app_id, h["date"])

    apps = {}
    for key, section in snap.feeds.items():
        label = f"{genre_labels.get(section.genre, section.genre)} · {FEED_LABELS.get(section.feed_type, section.feed_type)}"
        for item in section.items:
            if item.id not in apps:
                apps[item.id] = {**asdict(item), "charts": [],
                                 "first_seen": first_seen.get(item.id, snap.date),
                                 "is_new": bool(history) and item.id not in first_seen}
            app = apps[item.id]
            if not app["release_date"] and item.release_date:
                app["release_date"] = item.release_date
            app["charts"].append({"key": key, "label": label,
                                   "rank": section.ranks[item.id], "genre": section.genre,
                                   "feed_type": section.feed_type})

    for app in apps.values():
        app["charts"].sort(key=lambda c: (c["rank"], c["key"]))
        app["best_chart"] = app["charts"][0]
        try:
            age = (today - date.fromisoformat(app["release_date"][:10])).days
            app["age_days"] = age if age >= 0 else None
        except (ValueError, TypeError):
            app["age_days"] = None

    windows = []
    for days in WINDOWS:
        baseline_date = (today - timedelta(days=days)).isoformat()
        baseline = by_date.get(baseline_date)
        compared = set(snap.feeds) & set(baseline["feeds"]) if baseline else set()
        baseline_ranks = {key: ranks_for(baseline["feeds"][key]) for key in compared}
        matched_apps = set()
        movers = []
        for app in apps.values():
            signals = []
            for chart in app["charts"]:
                previous = baseline_ranks.get(chart["key"], {}).get(app["id"])
                if previous is None:
                    continue  # Absence is not rank 101 and gives no measured gain.
                matched_apps.add(app["id"])
                gain = previous - chart["rank"]
                if gain <= 0:
                    continue
                observations = [(baseline_date, previous)]
                for offset in range(1, days):
                    day = (today - timedelta(days=days - offset)).isoformat()
                    feed = by_date.get(day, {}).get("feeds", {}).get(chart["key"])
                    rank = ranks_for(feed).get(app["id"]) if feed else None
                    observations.append((day, rank))
                observations.append((snap.date, chart["rank"]))
                # A streak must consist of consecutive calendar-day observations.
                streak = 0
                for (_, older), (_, newer) in reversed(list(zip(observations, observations[1:]))):
                    if older is None or newer is None or newer >= older:
                        break
                    streak += 1
                signals.append({**chart, "previous": previous, "gain": gain,
                                "streak": streak,
                                "pattern": movement_pattern(observations, streak),
                                "observations": [{"date": d, "rank": r} for d, r in observations],
                                "observed_days": sum(r is not None for _, r in observations)})
            if signals:
                signals.sort(key=signal_order)
                movers.append({**app, "signal": signals[0], "signals": signals,
                               "rising_charts": len(signals)})
        movers.sort(key=lambda a: (*signal_order(a["signal"]), a["id"]))
        windows.append({"days": days, "baseline_date": baseline_date,
                        "available": bool(compared), "compared_charts": len(compared),
                        "matched_apps": len(matched_apps), "total_movers": len(movers),
                        "shortlist": movers[:5], "movers": movers[5:25], "candidates": movers})

    # A separate discovery list has no implied momentum or market-size score.
    new_apps = [a for a in apps.values() if a["is_new"]]
    recent = [a for a in new_apps if a["age_days"] is not None and a["age_days"] <= 180]
    recent.sort(key=lambda a: (a["best_chart"]["rank"], a["age_days"], a["id"]))
    previous_date = history[-1]["date"] if history else None
    gap = (today - date.fromisoformat(previous_date)).days if previous_date else None
    preferred = next((w["days"] for d in (7, 3, 1, 30) for w in windows
                      if w["days"] == d and w["available"]), 7)
    # All candidates reach the browser: filters must run before selecting five,
    # and must select evidence from the chart that actually matches the filter.
    eligible_ids = {a["id"] for w in windows for a in w["candidates"]} | {a["id"] for a in recent}
    charts = {key: {"label": f"{genre_labels.get(sec.genre, sec.genre)} · {FEED_LABELS.get(sec.feed_type, sec.feed_type)}",
                    "genre": sec.genre, "feed_type": sec.feed_type}
              for key, sec in snap.feeds.items()}
    filter_data = {
        "date": snap.date, "country": snap.country,
        # Saved apps must remain trackable even when they are not climbers or
        # fresh discoveries. Keep this catalog compact (no duplicated artwork).
        "tracking": {app_id: {k: app[k] for k in ("id", "name", "artist", "url", "charts")}
                     for app_id, app in apps.items()},
        "apps": {app_id: apps[app_id] for app_id in sorted(eligible_ids)},
        "charts": charts, "discoveries": [a["id"] for a in recent],
        "windows": [{"days": w["days"], "baseline_date": w["baseline_date"],
                     "available": w["available"], "candidates": [
                         {"id": a["id"], "signals": [
                             {**{k: s[k] for k in ("key", "rank", "previous", "gain", "streak", "pattern", "observed_days")},
                              "ranks": [p["rank"] for p in s["observations"]]}
                             for s in a["signals"]]} for a in w["candidates"]]}
                    for w in windows],
    }
    return {"total_apps": len(apps), "total_charts": len(snap.feeds),
            "new_ids": sorted(a["id"] for a in new_apps), "windows": windows,
            "default_window": preferred, "discoveries": recent[:5],
            "recent_count": len(recent), "previous_date": previous_date, "gap_days": gap,
            "baseline": not bool(history), "filter_data": filter_data}
