#!/usr/bin/env python3
from pathlib import Path
from .config import AppConfig
from .tracker import Top100Tracker


def main():
    root = Path(__file__).resolve().parents[1]
    cfg = AppConfig.load(root / "config.yaml")
    t = Top100Tracker(cfg, workspace=root)
    t.run_once()


if __name__ == "__main__":
    main()
