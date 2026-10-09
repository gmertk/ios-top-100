#!/usr/bin/env python3
from pathlib import Path
import argparse
import logging
from .apple_client import AppleFeedClient, FeedError
from .config import AppConfig
from .tracker import Top100Tracker


def main():
    parser = argparse.ArgumentParser(description="Track new entrants in Apple charts.")
    parser.add_argument("--check-feeds", action="store_true",
                        help="Check every configured feed without writing files or sending notifications.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(__file__).resolve().parents[1]
    cfg = AppConfig.load(root / "config.yaml")
    if args.check_feeds:
        client = AppleFeedClient(cfg.country)
        checked = failed = 0
        for feed in cfg.feeds:
            for genre in feed["genres"]:
                checked += 1
                key = f"{feed['type']}:{genre}"
                try:
                    section = client.fetch_section(feed["type"], str(genre))
                    print(f"OK {key}: {len(section.items)} apps", flush=True)
                except FeedError as exc:
                    failed += 1
                    print(f"FAIL {key}: {exc}", flush=True)
        print(f"{checked - failed}/{checked} feeds healthy")
        return 1 if failed else 0
    t = Top100Tracker(cfg, workspace=root)
    t.run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
