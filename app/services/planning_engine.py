from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


DONE_STATUSES = {"completed", "done", "cancelled"}
HIGH_ENERGY = {"high", "deep", "focus"}
LOW_ENERGY = {"low", "light", "admin"}
DEFAULT_WORK_WINDOWS = [(time(9), time(12)), (time(13), time(17)), (time(19), time(21))]
DEFAULT_SLEEP = (time(23), time(7))


@dataclass
class Slot:
    start: datetime
    end: datetime


class PlanningEngine:
    def __init__(self, events, metadata_loader, today=None):
        self.events = list(events)
        self.metadata_loader = metadata_loader
        self.today = today or date.today()
        self.metadata = {event.id: metadata_loader(event) for event in self.events}
        self.done_keys = {
            key
            for event in self.events
            for key in self._event_keys(event)
            if event.status in DONE_STATUSES
        }

    def build(self):
        scheduled = self._schedule_events()
        return {
            "today": [self._serialize(block) for block in scheduled if block["start"].date() == self.today],
            "tomorrow": [
                self._serialize(block)
                for block in scheduled
                if block["start"].date() == self.today + timedelta(days=1)
            ],
            "week": [
                self._serialize(block)
                for block in scheduled
                if self.today <= block["start"].date() <= self.today + timedelta(days=6)
            ][:16],
            "next_week": [
                self._serialize(block)
                for block in scheduled
                if self.today + timedelta(days=7) <= block["start"].date() <= self.today + timedelta(days=13)
            ][:16],
            "month": [
                self._serialize(block)
                for block in scheduled
                if self.today <= block["start"].date() <= self.today + timedelta(days=30)
            ][:30],
        }

    def _schedule_events(self):
        active = [event for event in self.events if event.status not in DONE_STATUSES]
        candidates = [event for event in active if self._dependencies_done(event)]
        candidates.sort(key=self._priority_key)
        occupied = self._base_occupied_slots()
        scheduled = []
        for event in candidates:
            minutes = self._remaining_minutes(event)
            if minutes <= 0:
                continue
            slot = self._find_slot(event, minutes, occupied)
            if not slot:
                continue
            occupied.setdefault(slot.start.date(), []).append(slot)
            occupied[slot.start.date()].sort(key=lambda item: item.start)
            scheduled.append({"event": event, "start": slot.start, "duration_minutes": minutes})
        scheduled.sort(key=lambda item: item["start"])
        return scheduled

    def _find_slot(self, event, minutes, occupied):
        preferred = event.planned_start.date() if event.planned_start else None
        latest = self._latest_date(event)
        earliest = self.today
        target = self._target_date(event, earliest, latest)
        search_dates = self._candidate_dates(preferred, target, earliest, latest)
        for day in search_dates:
            for window in self._work_windows(event, day):
                for slot in self._slots_in_window(window, minutes, event):
                    if slot.end.date() != day:
                        continue
                    if event.deadline and slot.end > event.deadline:
                        continue
                    if self._overlaps(slot, [self._sleep_window(self.metadata.get(event.id, {}), day)]):
                        continue
                    if not self._overlaps(slot, occupied.get(day, [])):
                        return slot
        return None

    def _candidate_dates(self, preferred, target, earliest, latest):
        dates = []
        if preferred and earliest <= preferred <= latest:
            dates.append(preferred)
        if target and earliest <= target <= latest and target not in dates:
            dates.append(target)
        cursor = earliest
        while cursor <= latest:
            if cursor not in dates:
                dates.append(cursor)
            cursor += timedelta(days=1)
        return dates

    def _target_date(self, event, earliest, latest):
        if not event.deadline:
            return preferred if (preferred := event.planned_start.date() if event.planned_start else None) else earliest
        progress = self._progress(event)
        days_before = {
            "hackathon": 3 if progress < 0.6 else 2,
            "application": 1,
            "goal": 1,
            "repo": 2 if progress < 0.6 else 1,
            "learning_video": 1,
        }.get(event.event_type, 0)
        target = event.deadline.date() - timedelta(days=days_before)
        return min(max(target, earliest), latest)

    def _work_windows(self, event, day):
        metadata = self.metadata.get(event.id, {})
        windows = metadata.get("preferred_working_hours") or metadata.get("working_hours")
        parsed = [window for window in (self._parse_window(item, day) for item in windows or []) if window]
        if not parsed:
            parsed = [(datetime.combine(day, start), datetime.combine(day, end)) for start, end in DEFAULT_WORK_WINDOWS]
        sleep = self._sleep_window(metadata, day)
        return [window for window in parsed if not self._window_blocked_by_sleep(window, sleep)]

    def _slots_in_window(self, window, minutes, event):
        start, end = window
        metadata = self.metadata.get(event.id, {})
        break_minutes = int(metadata.get("break_minutes") or 10)
        step = 15
        if self._energy(event) in HIGH_ENERGY:
            start = max(start, datetime.combine(start.date(), time(9)))
            end = min(end, datetime.combine(start.date(), time(14)))
        elif self._energy(event) in LOW_ENERGY:
            start = max(start, datetime.combine(start.date(), time(13)))
        cursor = start
        while cursor + timedelta(minutes=minutes) <= end:
            yield Slot(cursor, cursor + timedelta(minutes=minutes + break_minutes))
            cursor += timedelta(minutes=step)

    def _base_occupied_slots(self):
        occupied = {}
        for event in self.events:
            metadata = self.metadata.get(event.id, {})
            for item in metadata.get("calendar_events") or []:
                slot = self._parse_calendar_slot(item)
                if slot:
                    occupied.setdefault(slot.start.date(), []).append(slot)
            if event.event_type == "meeting" and event.planned_start:
                minutes = max(15, int(event.planned_minutes or 45))
                slot = Slot(event.planned_start, event.planned_start + timedelta(minutes=minutes))
                occupied.setdefault(slot.start.date(), []).append(slot)
        for slots in occupied.values():
            slots.sort(key=lambda item: item.start)
        return occupied

    def _priority_key(self, event):
        deadline = event.deadline or datetime.combine(self.today + timedelta(days=365), time(23, 59))
        days_left = (deadline.date() - self.today).days
        progress = self._progress(event)
        risk_rank = 0 if days_left <= 1 else 1 if days_left <= 3 and progress < 0.8 else 2 if days_left <= 7 else 3
        priority_rank = {"urgent": 0, "high": 1, "normal": 2, "medium": 2, "low": 3}.get(
            str(event.priority or "normal").lower(),
            2,
        )
        difficulty_rank = {"hard": 0, "high": 0, "medium": 1, "normal": 1, "low": 2, "easy": 2}.get(
            self._difficulty(event),
            1,
        )
        event_rank = {
            "hackathon": 0,
            "application": 0,
            "repo": 1,
            "email": 2,
            "goal": 3,
            "learning": 4,
            "learning_video": 4,
        }.get(event.event_type, 5)
        return (risk_rank, deadline, priority_rank, difficulty_rank, event_rank)

    def _remaining_minutes(self, event):
        minutes = max(5, int(event.planned_minutes or 45))
        metadata = self.metadata.get(event.id, {})
        estimated_hours = metadata.get("estimated_hours")
        if estimated_hours not in (None, ""):
            try:
                minutes = max(minutes, int(float(estimated_hours) * 60))
            except (TypeError, ValueError):
                pass
        progress_value = self._progress(event)
        return max(0, int(round(minutes * (1.0 - progress_value))))

    def _dependencies_done(self, event):
        dependencies = self.metadata.get(event.id, {}).get("dependencies") or []
        return all(str(item) in self.done_keys for item in dependencies)

    def _latest_date(self, event):
        if event.deadline and event.deadline.date() >= self.today:
            return event.deadline.date()
        return self.today + timedelta(days=30)

    def _serialize(self, block):
        event = block["event"]
        metadata = self.metadata.get(event.id, {})
        days_left = (event.deadline.date() - self.today).days if event.deadline else None
        return {
            "event_id": event.id,
            "title": event.title,
            "project": event.project or "",
            "event_type": event.event_type,
            "start": block["start"].isoformat(),
            "duration_minutes": block["duration_minutes"],
            "deadline": event.deadline.isoformat() if event.deadline else None,
            "next_action": event.work_left or event.next_question or "",
            "status": event.status,
            "reason": self._reason(event, days_left),
            "days_left": days_left,
            "progress": round(self._progress(event) * 100),
            "source_signals": metadata.get("source_signals") or [],
        }

    def _progress(self, event):
        progress = self.metadata.get(event.id, {}).get("progress")
        if progress in (None, ""):
            return 1.0 if event.status in DONE_STATUSES else 0.0
        try:
            value = float(progress)
            if value > 1:
                value /= 100
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            return 0.0

    def _reason(self, event, days_left):
        progress = round(self._progress(event) * 100)
        if days_left is not None and days_left <= 0:
            return "Due today or overdue, so this block is placed first."
        if event.event_type == "application":
            return f"A hiring step is waiting{f' with {days_left} days left' if days_left is not None else ''}."
        if event.event_type in {"hackathon", "repo"} and days_left is not None:
            return f"{days_left} days remain and tracked progress is {progress}%."
        if event.priority in {"urgent", "high"}:
            return "High-priority work selected from your connected local signals."
        return "Scheduled from the nearest available work window."

    def _event_keys(self, event):
        return {str(event.id), event.source_key or "", event.title or ""}

    def _energy(self, event):
        return str(self.metadata.get(event.id, {}).get("energy_level") or "").lower()

    def _difficulty(self, event):
        return str(self.metadata.get(event.id, {}).get("difficulty") or "normal").lower()

    def _sleep_window(self, metadata, day):
        sleep = metadata.get("sleep_schedule") or {}
        start = self._parse_time(sleep.get("start")) if isinstance(sleep, dict) else None
        end = self._parse_time(sleep.get("end")) if isinstance(sleep, dict) else None
        start = start or DEFAULT_SLEEP[0]
        end = end or DEFAULT_SLEEP[1]
        sleep_start = datetime.combine(day, start)
        sleep_end = datetime.combine(day, end)
        if sleep_end <= sleep_start:
            sleep_end += timedelta(days=1)
        return Slot(sleep_start, sleep_end)

    def _window_blocked_by_sleep(self, window, sleep):
        return window[0] >= sleep.start and window[1] <= sleep.end

    def _parse_window(self, value, day):
        if not isinstance(value, dict):
            return None
        start = self._parse_time(value.get("start"))
        end = self._parse_time(value.get("end"))
        if not start or not end:
            return None
        return (datetime.combine(day, start), datetime.combine(day, end))

    def _parse_calendar_slot(self, value):
        if not isinstance(value, dict):
            return None
        start = self._parse_datetime(value.get("start"))
        end = self._parse_datetime(value.get("end"))
        if not start or not end or end <= start:
            return None
        return Slot(start, end)

    def _parse_datetime(self, value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None

    def _parse_time(self, value):
        try:
            return time.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    def _overlaps(self, slot, slots):
        return any(slot.start < existing.end and slot.end > existing.start for existing in slots)
