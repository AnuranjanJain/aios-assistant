"""Account-aware routing for local Gmail intelligence.

The same sender can mean different things in different inboxes. These rules
make the user's three known accounts explicit while keeping unknown accounts
safe and reviewable.
"""

from __future__ import annotations

import os
import re


PRIMARY_ACCOUNT_ENV = "AIOS_PRIMARY_ACCOUNT"
GENERAL_ACCOUNT_ENV = "AIOS_GENERAL_ACCOUNT"

ACCOUNT_ROLE_LABELS = {
    "primary": "Primary career inbox",
    "campus": "VIT campus inbox",
    "general": "General inbox",
}


def account_role(email: str | None, account_label: str | None = "") -> str:
    value = str(email or "").strip().lower()
    primary = os.getenv(PRIMARY_ACCOUNT_ENV, "").strip().lower()
    general = os.getenv(GENERAL_ACCOUNT_ENV, "").strip().lower()
    label = str(account_label or "").strip().lower()
    if primary and value == primary:
        return "primary"
    if general and value == general:
        return "general"
    if value.endswith("@vitbhopal.ac.in") or "campus" in label or "vit placement" in label:
        return "campus"
    if any(token in label for token in ("career", "primary", "job")):
        return "primary"
    if any(token in label for token in ("general", "personal", "hackathon")):
        return "general"
    return "general"


def account_policy(email: str | None, account_label: str | None = "") -> dict[str, object]:
    role = account_role(email, account_label=account_label)
    return {
        "email": str(email or "").strip().lower(),
        "role": role,
        "label": ACCOUNT_ROLE_LABELS[role],
        "purpose": {
            "primary": "Personal jobs, freelance work, assessments, interviews, and off-campus applications.",
            "campus": "VIT placement drives, eligibility notices, PAT and campus meetings.",
            "general": "General mail, job platforms, hackathons, Devpost, Unstop, and PromptWars.",
        }[role],
    }


def classify_source_mail(*, account_email, sender, subject, body, sent_at=None, account_label=""):
    """Return a source-specific signal or ``None`` for ordinary mail."""

    role = account_role(account_email, account_label=account_label)
    text = _clean(f"{sender} {subject} {body}")
    if role == "campus":
        meeting_signal = _has(text, "meeting", "pre placement talk", "ppt", "reporting time", "venue", "session", "orientation")
        opportunity_signal = _has(text, "eligible", "placement drive", "internship registration", "job registration", "selection list", "next round", "registration", "campus recruitment")
        if meeting_signal and not opportunity_signal:
            return {
                "kind": "campus_meeting",
                "source_role": role,
                "company": extract_campus_company(subject) or "VIT placement meeting",
                "state": "meeting",
                "occurred_at": sent_at,
                "next_action": "Check today's meeting time, venue, and required documents.",
                "summary": _compact_summary(body or subject),
            }
        if _has(text, "god bless you", "god bless", "gbu", "eligible", "placement drive", "internship registration", "job registration", "selection list", "next round", "pre placement talk", "campus recruitment"):
            company = extract_campus_company(subject) or extract_campus_company(body) or "Campus placement"
            state = _campus_state(text)
            return {
                "kind": "campus_opportunity",
                "source_role": role,
                "company": company,
                "state": state,
                "stage": _campus_stage(text, state),
                "occurred_at": sent_at,
                "next_action": _campus_next_action(state, company),
                "summary": _compact_summary(body or subject),
                "requirements": extract_requirements(text),
                "details": extract_campus_details(text),
                "eligibility": evaluate_company_eligibility(text, {}),
            }
    general_hackathon_signal = _has(text, "hackathon", "buildathon", "datathon", "devpost", "hack2skill", "promptwars") or (
        _has(text, "unstop", "hackerearth")
        and _has(text, "challenge", "competition", "contest", "registration", "submission", "round")
    )
    if role == "general" and general_hackathon_signal:
        status = "applied" if _has(text, "registered", "registration confirmed", "submission received", "submitted", "team request") else "discovered"
        return {
            "kind": "hackathon_mail",
            "source_role": role,
            "company": _hackathon_name(subject),
            "state": status,
            "stage": "submitted" if _has(text, "submission received", "submitted") else status,
            "occurred_at": sent_at,
            "next_action": "Open the event page and decide whether to apply." if status == "discovered" else "Track the next round, deadline, or submission status.",
            "summary": _compact_summary(body or subject),
        }
    return None


def extract_campus_company(text: str | None) -> str:
    value = str(text or "")
    patterns = (
        r"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,5})\s+next\s+round\b",
        r"(?:eligible for|registration|drive|selection list|interview).*?\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,5})\s+(?:placement|internship|hiring|drive|selection)",
        r"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,5})\s+(?:interview|placement drive)\b",
        r"\b(?:for|at|of)\s+([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,5})\s+(?:placement|internship|drive)",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return _clean_company(match.group(1))
    known = re.search(r"\b(Whirlpool|EY GDS|Infosys|Embitel|Sandisk|RFPIO|American Express|ANKO|Jio-bp|Aditya Birla|Voxela|BNP Paribas)\b", value, re.I)
    return _clean_company(known.group(1)) if known else ""


def evaluate_company_eligibility(text: str | None, profile: dict[str, object]) -> dict[str, object]:
    value = _clean(text)
    profile = profile or {}
    profile_values = {
        "10th_percentage": profile.get("10th_percentage", profile.get("tenth_percentage")),
        "12th_percentage": profile.get("12th_percentage", profile.get("twelfth_percentage")),
        "ug_percentage": profile.get("ug_percentage"),
        "degree": profile.get("degree"),
        "branch": profile.get("branch"),
        "campus": profile.get("campus"),
    }
    missing = [key for key, item in profile_values.items() if not item]
    reasons = []
    tenth = _percentage_requirement(value, "10th")
    twelfth = _percentage_requirement(value, "12th")
    tenth_value = profile_values["10th_percentage"]
    twelfth_value = profile_values["12th_percentage"]
    if tenth and tenth_value and float(tenth_value) < tenth:
        reasons.append(f"10th percentage is below the {tenth:g}% requirement.")
    if twelfth and twelfth_value and float(twelfth_value) < twelfth:
        reasons.append(f"12th percentage is below the {twelfth:g}% requirement.")
    required_degree = _required_degree(value)
    if required_degree and profile_values["degree"] and not _same_education(required_degree, str(profile_values["degree"])):
        reasons.append(f"Requires {required_degree}; profile says {profile_values['degree']}.")
    required_branch = _required_branch(value)
    if required_branch and profile_values["branch"] and not _same_branch(required_branch, str(profile_values["branch"])):
        reasons.append(f"Requires {required_branch}; profile says {profile_values['branch']}.")
    required_campus = _required_campus(value)
    if required_campus and profile_values["campus"] and not _same_campus(required_campus, str(profile_values["campus"])):
        reasons.append(f"Drive is for {required_campus}; profile says {profile_values['campus']}.")
    return {
        "status": "not_eligible" if reasons else "profile_incomplete" if missing else "eligible",
        "missing": missing,
        "reasons": reasons,
        "requirements": {
            "tenth_percentage": tenth,
            "twelfth_percentage": twelfth,
            "degree": required_degree,
            "branch": required_branch,
            "campus": required_campus,
        },
    }


def extract_requirements(text: str | None) -> list[str]:
    value = _clean(text)
    found = []
    for label, pattern in (("10th", r"10th.{0,40}(?:minimum|min|percent|%)"), ("12th", r"12th.{0,40}(?:minimum|min|percent|%)"), ("degree", r"b\.?tech|m\.?tech|mca|mba"), ("branch", r"cse|aiml|cyber|ece|mechanical|aerospace"), ("campus", r"vit bhopal|vit ap|vit chennai|vit vellore")):
        if re.search(pattern, value, re.I):
            found.append(label)
    return found


def extract_campus_details(text: str | None) -> dict[str, object]:
    value = _clean(text)
    package = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per annum|pa)?)\b", value, re.I)
    if _has(value, "physical", "offline", "venue", "reporting at"):
        mode = "physical"
    elif _has(value, "online", "virtual", "remote"):
        mode = "virtual"
    else:
        mode = "unspecified"
    location_match = re.search(r"\b(vellore|chennai|bengaluru|bangalore|bhopal|hyderabad|pune|mumbai|delhi)\b", value, re.I)
    round_match = re.search(r"\b(round\s*[1-9]|r[1-9]|interview|assessment|online test|pre placement talk)\b", value, re.I)
    return {
        "package_lpa": float(package.group(1)) if package else None,
        "mode": mode,
        "location": location_match.group(1).title() if location_match else "",
        "round": round_match.group(1) if round_match else "",
    }


def _campus_state(text):
    if _has(text, "not interested", "do not wish", "declined", "discarded"):
        return "skipped"
    if _has(text, "selected", "shortlisted", "next round", "interview", "assessment", "test"):
        return "selected"
    if _has(text, "applied", "registration confirmed", "registered"):
        return "applied"
    return "to_apply"


def _campus_stage(text, state):
    if _has(text, "interview"):
        return "interview"
    if _has(text, "assessment", "online test", "coding test"):
        return "assessment"
    if _has(text, "next round", "selected", "shortlisted"):
        return "shortlisted"
    return state


def _campus_next_action(state, company):
    return {
        "to_apply": f"Register for {company} after checking your eligibility and the campus registration deadline.",
        "applied": f"Track {company} for the next round or assessment mail.",
        "selected": f"Prepare the next {company} round and check the venue or assessment link.",
        "skipped": f"You marked {company} as skipped; reopen it only if your interest changes.",
    }.get(state, f"Review the latest {company} update.")


def _hackathon_name(subject):
    value = re.sub(r"^(re|fwd|fw):\s*", "", str(subject or ""), flags=re.I).strip()
    if re.search(r"prompt\s*wars", value, re.I):
        return "PromptWars"
    return value.split("|", 1)[0][:120] or "Hackathon"


def _percentage_requirement(text, label):
    match = re.search(rf"{re.escape(label)}.{0,60}?(\d{{2}}(?:\.\d+)?)\s*%", text, re.I)
    if not match:
        match = re.search(rf"(\d{{2}}(?:\.\d+)?)\s*%.{{0,60}}?{re.escape(label)}", text, re.I)
    return float(match.group(1)) if match else None


def _required_degree(text):
    match = re.search(r"\b(b\.?\s*tech|m\.?\s*tech|mca|mba)\b", text, re.I)
    return match.group(1).replace(" ", "").upper() if match else None


def _required_branch(text):
    match = re.search(r"\b(cse(?:\s*(?:core|aiml|ai/ml|cyber))?|ece(?:\s*(?:core|embedded))?|mechanical|aerospace)\b", text, re.I)
    return match.group(1).strip() if match else None


def _required_campus(text):
    match = re.search(r"\b(vit\s*(?:bhopal|ap|chennai|vellore))\b", text, re.I)
    return match.group(1).title() if match else None


def _same_education(required, actual):
    return required.replace(".", "").replace(" ", "").lower() in actual.replace(".", "").replace(" ", "").lower()


def _same_branch(required, actual):
    required = _clean(required).replace("ai/ml", "aiml")
    actual = _clean(actual).replace("ai/ml", "aiml")
    return required in actual or actual in required


def _same_campus(required, actual):
    return _clean(required) == _clean(actual)


def _clean_company(value):
    cleaned = re.sub(r"\s+", " ", value or "").strip(" .,:;|-—")
    cleaned = re.sub(r"\s+(?:placement|internship|hiring|registration|selection|drive)$", "", cleaned, flags=re.I)
    return cleaned[:120]


def _compact_summary(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:320]


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _has(text, *phrases):
    return any(phrase in text for phrase in phrases)
