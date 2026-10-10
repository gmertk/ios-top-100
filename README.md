# iOS App Radar

Tracks iOS App Store chart momentum and newly observed apps. Runs daily and generates HTML discovery reports.

## Discovery and momentum

Each report offers 1-, 3-, 7-, and 30-day comparisons, a shortlist of five climbers, up to 20 additional movers, and five recently released discoveries. Previously seen apps remain eligible for momentum; each shortlist contains unique app IDs.

Momentum is the earlier rank minus the current rank in the **same country, category, and chart type**. The comparison requires the exact earlier date; an old snapshot is never substituted for missing history. Apps absent from the earlier chart have no measured gain. Sustained climbs (at least three consecutive daily improvements ending on the report date within the selected window) sort first, followed by gain, streak, and current rank. Each app uses its highest-priority matching chart. Charts are not weighted for market size, and rank movement does not establish organic growth, revenue, or product quality.

The report labels one-day rises, sustained climbs, jump-led rises, mixed movement, and limited history. Without a sustained streak, one daily gain accounting for at least 70% of net window gain is labeled jump-led, provided all daily observations are available. Missing observations break streaks and are never interpolated.

Opportunity filters cover category, free/paid chart type, release age, minimum rank gain, sustained-only momentum, and hiding games. Filtering runs over **every candidate before choosing five**, including selecting evidence from the matching category rather than an unrelated stronger chart. Age limits exclude unknown ages. Games are identified by appearances in the Games or game subcategory charts and hidden across their overall-chart appearances too.

Category, chart type, age, and hidden-item preferences also apply to fresh discoveries; gain and momentum filters only apply to climbers. Apps and developers can be hidden and restored. Preferences use browser-local storage shared across new report dates on the same site; they do not sync between devices or between localhost and GitHub Pages. With JavaScript disabled, reports show their unfiltered default shortlist.

Rank timelines show missing daily observations as gaps. Improvement streaks require consecutive calendar days with strictly better ranks. The interface reports comparison coverage and defaults to seven days when available, then three, one, or thirty days.

Fresh discoveries are newly observed apps with an Apple feed release date within 180 days, ordered by best current rank and then age. These are research candidates, not automatically validated business ideas. Unknown, invalid, and future release dates are excluded from this list.

Snapshots now save app metadata and explicit ranks alongside the original ordered IDs. Old snapshots remain readable using ID order as rank. Newly observed totals use distinct apps from prior dated snapshots in the same country; same-day reruns preserve these totals. Keep the full dated history to preserve first-observed dates. The first run without prior history establishes a baseline instead of labeling every app new.

Reports before this change retain their original category-based totals, which may include the same app more than once. Gaps cannot be backfilled from current charts.

## Opportunity notebook

Use **Save idea** on a discovery, climber card, or mover row to keep an app in your notebook. Add notes about its target user, problem, your proposed improvement, and a small demand experiment, then choose **Save notes**. Saved apps remain in the notebook when they leave the shortlist. Each report shows their positions across its configured charts, with changes since the saved report where comparable observations exist. Missing apps are marked unobserved, never assigned a rank.

The notebook is stored only in your browser, shared across report dates on the same site. Notes are never sent to GitHub and do not automatically sync between devices. **Export notebook** downloads a JSON backup; **Import notebook** merges new apps while preserving existing entries and notes. Save pending edits before exporting or importing. Backups include app details, the saved rank baseline, and notes; they exclude filters and hidden-item preferences. Keep a backup before clearing browser data. The notebook supports 200 apps and import files up to 5 MB. Removal can be undone during the current visit.

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

GitHub Actions runs daily at 06:05 UTC (07:05 in Dublin during summer time, 06:05 in winter). Scheduled starts can be delayed by GitHub.

Bookmark the live site: **https://gmertk.github.io/ios-top-100/**. Each successful run tests the tracker, fetches the charts, commits the report and history, and deploys that run's generated site to GitHub Pages. Your computer does not need to be running.

For an immediate refresh, open **Actions → Daily iOS Top100 Tracker → Run workflow → main**. Check that both `build` and `deploy` finish successfully. GitHub Pages must use **GitHub Actions** as its publishing source; the deployment job uses the `github-pages` environment.

The workflow also supports optional Telegram notifications through `TELEGRAM_BOT_TOKEN` and the settings in `config.yaml`.

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
node --test tests/test_*.js
```

## License

MIT
