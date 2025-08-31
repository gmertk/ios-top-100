import os
import requests


class TelegramNotifier:
    """Simple Telegram notifier. Provide bot token via env TELEGRAM_BOT_TOKEN."""

    def __init__(self, enabled: bool, chat_id: str):
        self.enabled = enabled
        self.chat_id = chat_id
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    def send(self, message: str) -> None:
        if not (self.enabled and self.token and self.chat_id):
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": message,
                      "disable_web_page_preview": True},
                timeout=20
            )
        except Exception as e:
            print("Telegram send failed:", e)
