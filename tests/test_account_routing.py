from datetime import datetime
from types import SimpleNamespace

from app.services.account_routing import (
    account_role,
    classify_source_mail,
    evaluate_company_eligibility,
    extract_campus_company,
)
from app.services.email_triage import classify_email_category


def test_account_roles_are_configurable_without_publishing_addresses(monkeypatch):
    monkeypatch.setenv("AIOS_PRIMARY_ACCOUNT", "primary@example.test")
    monkeypatch.setenv("AIOS_GENERAL_ACCOUNT", "general@example.test")
    assert account_role("primary@example.test") == "primary"
    assert account_role("student@vitbhopal.ac.in") == "campus"
    assert account_role("general@example.test") == "general"


def test_campus_eligible_mail_becomes_actionable_company_opportunity():
    subject = "Congratulations! You're Eligible for Whirlpool Placement Drive"
    body = "Register for the drive. Eligible campus: VIT Bhopal. Package: 12 LPA."

    result = classify_source_mail(
        account_email="student@vitbhopal.ac.in",
        sender="VIT CDC <noreply.cdcinfo@vitstudent.ac.in>",
        subject=subject,
        body=body,
        sent_at=datetime(2026, 9, 18),
    )

    assert result["kind"] == "campus_opportunity"
    assert result["state"] == "to_apply"
    assert result["company"] == "Whirlpool"
    assert "Register" in result["next_action"]


def test_campus_round_update_is_not_a_second_company():
    result = extract_campus_company(
        "Re: EY GDS next round of selection process is scheduled"
    )
    assert result == "EY GDS"


def test_eligibility_requires_profile_and_explains_mismatch():
    missing = evaluate_company_eligibility(
        "Requires B.Tech CSE, minimum 70% in 10th and 12th, VIT Bhopal",
        {},
    )
    assert missing["status"] == "profile_incomplete"
    assert "10th_percentage" in missing["missing"]

    blocked = evaluate_company_eligibility(
        "Requires B.Tech CSE, minimum 70% in 10th and 12th, VIT Bhopal",
        {
            "degree": "B.Tech",
            "branch": "CSE AI/ML",
            "campus": "VIT Bhopal",
            "tenth_percentage": 68,
            "twelfth_percentage": 85,
            "ug_percentage": 80,
        },
    )
    assert blocked["status"] == "not_eligible"
    assert any("10th" in reason for reason in blocked["reasons"])


def test_account_aware_triage_prioritizes_campus_and_general_source_rules():
    assert classify_email_category(
        sender="VIT CDC <cdc@vitstudent.ac.in>",
        subject="Pre Placement Talk: Whirlpool",
        body="Reporting time 10:00 AM at venue AB-1.",
        account_email="student@vitbhopal.ac.in",
    ) == "meeting"
    assert classify_email_category(
        sender="Devpost <notifications@devpost.com>",
        subject="PromptWars registration confirmed",
        body="Your hackathon submission is registered.",
        account_email="general@example.test",
    ) == "hackathon"
    assert classify_email_category(
        sender="Unstop <alerts@unstop.com>",
        subject="Jobs matching your profile",
        body="New internship opportunities are available.",
        account_email="general@example.test",
    ) != "hackathon"


def test_campus_source_becomes_shared_application_signal_without_marking_it_applied():
    from app.services.application_intelligence import classify_campus_email

    email = SimpleNamespace(
        account=SimpleNamespace(email="student@vitbhopal.ac.in", label="VIT campus"),
        sender="VIT CDC <cdc@vitstudent.ac.in>",
        subject="Congratulations! You're Eligible for Whirlpool Placement Drive",
        snippet="Register for the drive. VIT Bhopal. Package 12 LPA.",
        body_text="",
        sent_at=datetime(2026, 9, 18),
        created_at=datetime(2026, 9, 18),
    )
    result = classify_campus_email(email, {
        "10th_percentage": 80,
        "12th_percentage": 80,
        "ug_percentage": 75,
        "degree": "B.Tech",
        "branch": "CSE",
        "campus": "VIT Bhopal",
    })

    assert result["company"] == "Whirlpool"
    assert result["stage"] == "to_apply"
    assert result["eligibility"]["status"] == "eligible"
    assert result["campus_details"]["package_lpa"] == 12.0
