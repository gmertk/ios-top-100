# iOS App Radar

Tracks iOS App Store chart momentum and newly observed apps. Runs daily and generates HTML discovery reports.

## Discovery and momentum

Each report offers 1-, 3-, 7-, and 30-day comparisons, a shortlist of five climbers, up to 20 additional movers, and five recently released discoveries. Previously seen apps remain eligible for momentum; each shortlist contains unique app IDs.

Momentum is the earlier rank minus the current rank in the **same country, category, and chart type**. The comparison requires the exact earlier date; an old snapshot is never substituted for missing history. Apps absent from the earlier chart have no measured gain. Candidate selection uses the app's largest positive chart gain, then its consecutive daily improvement streak and current rank. Charts are not weighted for market size, and rank movement does not establish organic growth, revenue, or product quality.

Rank timelines show missing daily observations as gaps. Improvement streaks require consecutive calendar days with strictly better ranks. The interface reports comparison coverage and defaults to seven days when available, then three, one, or thirty days.

Fresh discoveries are newly observed apps with an Apple feed release date within 180 days, ordered by best current rank and then age. These are research candidates, not automatically validated business ideas. Unknown, invalid, and future release dates are excluded from this list.

Snapshots now save app metadata and explicit ranks alongside the original ordered IDs. Old snapshots remain readable using ID order as rank. Newly observed totals use distinct apps from prior dated snapshots in the same country; same-day reruns preserve these totals. Keep the full dated history to preserve first-observed dates. The first run without prior history establishes a baseline instead of labeling every app new.

Reports before this change retain their original category-based totals, which may include the same app more than once. Gaps cannot be backfilled from current charts.

## Setup

```bash
pip install -r requirements.txt
```

Edit `config.yaml` for country and Telegram settings.

## Usage

```bash
python -m tracker.main
```

## Automation

GitHub Actions runs daily at 06:05 UTC. Set `TELEGRAM_BOT_TOKEN` secret for notifications.

## Feed health and recovery

Check every configured chart without changing reports, the seen-app registry, or sending notifications:

```bash
python -m tracker.main --check-feeds
```

The command prints each chart's result and exits nonzero if any fail. Apple sometimes returns fewer than 100 apps, especially in smaller paid categories; nonempty shorter charts are accepted.

Overall charts use Apple's RSS v2 endpoint at `rss.marketingtools.apple.com`, with the legacy iTunes overall chart as a fallback. Category charts use the legacy iTunes genre feeds. Filtering the overall Top 100 by genre is not a replacement for a category's Top 100.

Requests retry connection failures, rate limiting, and temporary server errors up to three times with backoff. Empty or malformed charts fail explicitly. A failed chart stops publication before history or the seen-app registry is changed, so missing data is not reported as zero new apps. Logs identify the chart that failed.

If reports stop, inspect the **Daily iOS Top100 Tracker** run in GitHub Actions. After deploying a fix, use **Run workflow** to verify fetching and Pages deployment. Check that scheduled runs are enabled; a successful local feed check alone does not restore hosted automation.

“First-ever” means first observed by this tracker across its configured charts, not first-ever in App Store history. After a reporting gap, newly observed apps cannot be assigned an actual entry date within that gap.

Run regression checks with:

```bash
python -m unittest discover -s tests -v
```

## License

MIT
