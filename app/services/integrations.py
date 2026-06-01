class GmailClient:
    def fetch_recent_messages(self):
        raise NotImplementedError("Add Gmail API OAuth flow here.")


class CalendarClient:
    def create_event(self, title, start_at, end_at):
        raise NotImplementedError("Add Google Calendar API integration here.")


class TelegramNotifier:
    def send(self, message):
        raise NotImplementedError("Add Telegram Bot API integration here.")
