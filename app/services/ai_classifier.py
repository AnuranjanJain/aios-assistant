import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class Classification:
    category: str
    status: str
    confidence: float
    reason: str
    title: str = ""
    organization: str = ""
    action_needed: str = ""
    deadline: str = ""


class RuleBasedClassifier:
    def classify(self, subject: str, body: str = "") -> Classification:
        text = f"{subject} {body}".lower()

        rules = [
            ("interview", "Interview Scheduled", ["interview", "technical round", "hr round"]),
            ("job", "OA Received", ["online assessment", "coding assessment", "oa"]),
            ("job", "Rejected", ["unfortunately", "not moving forward", "rejection"]),
            ("job", "Applied", ["application received", "thank you for applying", "applied"]),
            ("hackathon", "Registration", ["hackathon", "devfolio", "unstop"]),
            ("deadline", "Deadline", ["deadline", "due date", "submission"]),
            ("meeting", "Meeting", ["meeting", "calendar invite", "schedule a call"]),
        ]

        for category, status, keywords in rules:
            if any(keyword in text for keyword in keywords):
                return Classification(
                    category=category,
                    status=status,
                    confidence=0.82,
                    reason=f"Matched keywords: {', '.join(keywords)}",
                    title=subject[:180],
                )

        return Classification(
            category="general",
            status="Review",
            confidence=0.35,
            reason="No strong productivity signal found.",
            title=subject[:180],
        )


class OllamaClassifier:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback = RuleBasedClassifier()

    def classify(self, subject: str, body: str = "") -> Classification:
        prompt = self._build_prompt(subject, body)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }

        try:
            request = Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
            return self._parse_response(data.get("response", ""), subject)
        except (OSError, URLError, json.JSONDecodeError, KeyError, ValueError) as exc:
            fallback = self.fallback.classify(subject, body)
            fallback.reason = f"Local model unavailable or invalid response. Fallback used: {exc}"
            return fallback

    def _build_prompt(self, subject: str, body: str) -> str:
        return f"""
You are a local productivity agent. Classify this email/page text for a student career assistant.

Return only valid JSON with these keys:
category: one of job, interview, hackathon, deadline, meeting, wellbeing, general
status: short status such as Applied, Interview Scheduled, Rejected, Registration, Deadline, Review
title: concise title
organization: company, sender, platform, or empty string
action_needed: concrete next action or empty string
deadline: ISO-like date/time if present, otherwise empty string
confidence: number from 0 to 1
reason: short explanation

Subject:
{subject}

Body:
{body[:4000]}
""".strip()

    def _parse_response(self, response_text: str, subject: str) -> Classification:
        payload = json.loads(response_text)
        return Classification(
            category=str(payload.get("category", "general")).lower(),
            status=str(payload.get("status", "Review")),
            confidence=float(payload.get("confidence", 0.5)),
            reason=str(payload.get("reason", "Local model classification.")),
            title=str(payload.get("title", subject[:180]))[:180],
            organization=str(payload.get("organization", ""))[:120],
            action_needed=str(payload.get("action_needed", "")),
            deadline=str(payload.get("deadline", "")),
        )


def get_classifier(provider: str = "rule_based", base_url: str = "", model: str = ""):
    if provider == "ollama":
        return OllamaClassifier(base_url or "http://localhost:11434", model or "qwen2.5:7b")
    return RuleBasedClassifier()
