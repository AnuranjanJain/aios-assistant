from datetime import datetime


def build_daily_plan(opportunities, reminders):
    today = datetime.utcnow().date()
    due_today = [item for item in reminders if item.due_at.date() == today and not item.is_done]
    interviews = [item for item in opportunities if "interview" in item.status.lower()]
    hackathons = [item for item in opportunities if item.kind == "hackathon"]

    focus_blocks = []

    if interviews:
        focus_blocks.append("90 min interview prep")
    if hackathons:
        focus_blocks.append("60 min hackathon/project progress")
    if due_today:
        focus_blocks.append("45 min deadline cleanup")

    focus_blocks.append("45 min DSA practice")

    return {
        "summary": f"{len(due_today)} reminders due today, {len(interviews)} interview items, {len(hackathons)} hackathon items.",
        "focus_blocks": focus_blocks,
        "recommended_order": [
            "Clear urgent reminders",
            "Handle interview or deadline work",
            "Do deep work/project block",
            "Finish with DSA practice",
        ],
    }
