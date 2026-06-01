FOCUS_CATEGORIES = {"coding", "study", "project", "interview_prep", "dsa", "deep_work"}
DISTRACTION_CATEGORIES = {"social", "short_video", "gaming", "entertainment"}


def summarize_activity(category, duration_minutes, planned_task="", actual_task=""):
    if category in DISTRACTION_CATEGORIES and duration_minutes >= 25:
        return "Focus drift detected. Start a short recovery block and move one planned task later if needed."

    if planned_task and actual_task and planned_task.lower() not in actual_task.lower():
        return "Actual activity does not match the planned task. Check whether the plan needs adjustment."

    if category in FOCUS_CATEGORIES:
        return "Good focus signal. Keep this block protected."

    return "Activity logged. Not enough signal for a strong recommendation yet."
