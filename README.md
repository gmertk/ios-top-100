# iOS Top 100 Tracker

Tracks first-ever entrants into iOS App Store Top 100 charts. Runs daily and generates HTML reports.

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

## License

MIT
