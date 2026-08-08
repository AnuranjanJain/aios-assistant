from app.services.email_triage import classify_email_category, triage_email


def test_job_alerts_do_not_become_actionable_deadlines():
    result = triage_email(
        sender="noreply@match.indeed.com",
        subject="Apply now: 12 new software jobs",
        body="Jobs for you. Apply today and explore recommended roles.",
        is_unread=True,
    )

    assert result.category == "career"
    assert result.priority == "low"
    assert result.urgency == "low"
    assert result.is_actionable is False


def test_personal_interview_is_high_priority_and_actionable():
    result = triage_email(
        sender="recruiting@example.com",
        subject="Your interview is scheduled for tomorrow",
        body="Please confirm your interview slot and prepare your portfolio.",
        is_unread=True,
    )

    assert result.category == "internship"
    assert result.priority == "high"
    assert result.is_actionable is True
    assert "action" in result.signals
    assert "deadline" not in result.signals


def test_selection_outcome_is_actionable_without_inflating_to_urgent():
    result = triage_email(
        sender="PromptWars <admin@hack2skill.com>",
        subject="You were selected for Round 2",
        body="Congratulations. Your next project brief is ready.",
    )

    assert result.category == "hackathon"
    assert result.priority == "high"
    assert result.is_actionable is True
    assert result.urgency == "high"
    assert "outcome" in result.signals


def test_category_detection_keeps_newsletter_interview_content_out_of_applications():
    category = classify_email_category(
        "updates@linkedin.com",
        "Interview tips and recommended jobs",
        "View in browser for interview preparation and new jobs for you.",
    )

    assert category == "career"
