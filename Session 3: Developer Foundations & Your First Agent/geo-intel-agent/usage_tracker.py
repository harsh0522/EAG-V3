"""
File-backed usage tracker. Persists daily counters to usage_data.json so both
the FastAPI server and the Telegram bot share the same counts.
"""

import json
import os
from datetime import date

USAGE_FILE = os.path.join(os.path.dirname(__file__), "usage_data.json")


class UsageTracker:
    LIMITS = {
        "youtube_searches_day":    100,
        "gemini_requests_day":     1500,
        "gemini_rpm":              30,
        "telegram_per_min":        20,
        "telegram_per_sec_global": 30,
    }

    def __init__(self):
        self._today = date.today()
        # daily counters (shared via file)
        self.youtube_searches_today = 0
        self.gemini_requests_today = 0
        self.gemini_tokens_today = 0
        self.telegram_messages_today = 0
        # session counters (in-memory only)
        self.gemini_tokens_session = 0
        self.gemini_requests_session = 0
        self.youtube_searches_session = 0
        self.telegram_messages_session = 0
        # last Telegram chat_id for auto-notifications
        self.last_telegram_chat_id = None
        self._load()

    def _load(self):
        try:
            with open(USAGE_FILE) as f:
                d = json.load(f)
            saved_date = date.fromisoformat(d.get("date", "2000-01-01"))
            if saved_date == date.today():
                self.youtube_searches_today = d.get("youtube_searches_today", 0)
                self.gemini_requests_today = d.get("gemini_requests_today", 0)
                self.gemini_tokens_today = d.get("gemini_tokens_today", 0)
                self.telegram_messages_today = d.get("telegram_messages_today", 0)
            self.last_telegram_chat_id = d.get("last_telegram_chat_id")
        except Exception:
            pass

    def _save(self):
        try:
            d = {
                "date": date.today().isoformat(),
                "youtube_searches_today": self.youtube_searches_today,
                "gemini_requests_today": self.gemini_requests_today,
                "gemini_tokens_today": self.gemini_tokens_today,
                "telegram_messages_today": self.telegram_messages_today,
                "last_telegram_chat_id": self.last_telegram_chat_id,
            }
            with open(USAGE_FILE, "w") as f:
                json.dump(d, f)
        except Exception:
            pass

    def _check_day_reset(self):
        today = date.today()
        if today != self._today:
            self._today = today
            self.youtube_searches_today = 0
            self.gemini_requests_today = 0
            self.gemini_tokens_today = 0
            self.telegram_messages_today = 0
            self._save()

    def record_youtube_search(self):
        self._check_day_reset()
        self.youtube_searches_today += 1
        self.youtube_searches_session += 1
        self._save()

    def record_gemini_call(self, tokens: int = 0):
        self._check_day_reset()
        self.gemini_requests_today += 1
        self.gemini_tokens_today += tokens
        self.gemini_requests_session += 1
        self.gemini_tokens_session += tokens
        self._save()

    def record_telegram_message(self, chat_id=None):
        self._check_day_reset()
        self.telegram_messages_today += 1
        self.telegram_messages_session += 1
        if chat_id is not None:
            self.last_telegram_chat_id = chat_id
        self._save()

    def snapshot(self) -> dict:
        self._check_day_reset()
        # Re-load from file to get counts from the other process
        self._load()

        yt_used = self.youtube_searches_today
        yt_limit = self.LIMITS["youtube_searches_day"]
        yt_pct = round((yt_used / yt_limit) * 100)

        gem_used = self.gemini_requests_today
        gem_limit = self.LIMITS["gemini_requests_day"]
        gem_pct = round((gem_used / gem_limit) * 100)

        tg_today = self.telegram_messages_today

        return {
            "youtube": {
                "searches_today": yt_used,
                "limit_day":      yt_limit,
                "pct":            yt_pct,
                "units_used":     yt_used * 100,
                "units_limit":    10000,
                "session":        self.youtube_searches_session,
                "resets":         "midnight PT / 1:30 PM IST",
            },
            "gemini": {
                "requests_today":  gem_used,
                "limit_day":       gem_limit,
                "pct":             gem_pct,
                "tokens_today":    self.gemini_tokens_today,
                "requests_session": self.gemini_requests_session,
                "tokens_session":  self.gemini_tokens_session,
                "rpm_limit":       self.LIMITS["gemini_rpm"],
                "model":           "gemini-2.0-flash-lite",
                "resets":          "midnight PT / 1:30 PM IST",
            },
            "telegram": {
                "messages_today":      tg_today,
                "messages_session":    self.telegram_messages_session,
                "limit_per_min":       self.LIMITS["telegram_per_min"],
                "limit_per_sec_global": self.LIMITS["telegram_per_sec_global"],
                "note":                "No daily cap — per-chat: 20 msg/min",
            },
        }


# Singleton shared within a process; file keeps cross-process state
tracker = UsageTracker()
