import re
import uuid
from urllib.parse import urlencode

from browser_agent.safety import BrowserSafety


SOURCE_URLS = {
    "linkedin": "https://www.linkedin.com/jobs/search/",
    "internshala": "https://internshala.com/internships/",
    "wellfound": "https://wellfound.com/jobs",
    "naukri": "https://www.naukri.com/",
    "indeed": "https://www.indeed.com/jobs",
}


class BrowserTaskPlanner:
    def __init__(self, safety: BrowserSafety):
        self.safety = safety

    def create(self, request_text, parameters=None):
        parameters = dict(parameters or {})
        request_text = (request_text or "").strip()
        if not request_text:
            raise ValueError("Describe the browser workflow.")
        lowered = request_text.lower()
        source = self._source(lowered, parameters.get("source"))
        query = parameters.get("query") or self._query(request_text)
        actions = []
        intent = "research"

        if "track my applications" in lowered or "application status" in lowered:
            intent = "track_applications"
            return self._plan(request_text, intent, [])

        application_intent = (
            "apply filters" not in lowered
            and any(term in lowered for term in ("apply to", "apply for", "fill form", "submit application"))
        )
        if application_intent:
            intent = "prepare_application"
            url = parameters.get("url")
            if not url:
                raise ValueError("Provide the exact job URL before preparing an application.")
            url = self.safety.validate_url(url)
            actions.extend(
                [
                    self._action("open", {"url": url}),
                    self._action("extract_page", {"kind": "job"}),
                    self._action(
                        "fill_form",
                        {
                            "fields": parameters.get("fields", {}),
                            "resume_version": parameters.get("resume_version", ""),
                            "cover_letter": parameters.get("cover_letter", ""),
                        },
                    ),
                    self._action("click_submit", {"selector": parameters.get("submit_selector", "")}),
                ]
            )
        else:
            intent = "job_search" if any(term in lowered for term in ("job", "intern", "hiring", "career")) else "research"
            url = self._search_url(source, query, parameters)
            actions.append(self._action("open", {"url": url}))
            actions.append(
                self._action(
                    "extract_jobs" if intent == "job_search" else "extract_page",
                    {
                        "source": source,
                        "query": query,
                        "max_results": min(100, int(parameters.get("max_results") or 25)),
                    },
                )
            )

        return self._plan(request_text, intent, actions)

    def _plan(self, request_text, intent, actions):
        risks = [action["risk_level"] for action in actions]
        risk = "critical" if "critical" in risks else "high" if "high" in risks else "medium" if "medium" in risks else "low"
        return {
            "id": uuid.uuid4().hex,
            "request": request_text,
            "intent": intent,
            "risk_level": risk,
            "actions": actions,
        }

    def _action(self, operation, arguments):
        return {
            "id": uuid.uuid4().hex,
            "operation": operation,
            "arguments": arguments,
            "risk_level": self.safety.action_risk(operation, arguments),
        }

    @staticmethod
    def _source(text, explicit):
        if explicit:
            return str(explicit).lower()
        return next((source for source in SOURCE_URLS if source in text), "indeed")

    @staticmethod
    def _query(text):
        cleaned = re.sub(r"\b(find|search|collect|research|jobs?|internships?|on linkedin|on indeed)\b", " ", text, flags=re.I)
        return " ".join(cleaned.split()) or "software internship"

    def _search_url(self, source, query, parameters):
        base = SOURCE_URLS.get(source, SOURCE_URLS["indeed"])
        if source == "linkedin":
            url = f"{base}?{urlencode({'keywords': query, 'location': parameters.get('location', '')})}"
        elif source == "indeed":
            url = f"{base}?{urlencode({'q': query, 'l': parameters.get('location', '')})}"
        elif source == "internshala":
            slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
            url = f"{base}{slug}-internship/"
        else:
            url = base
        return self.safety.validate_url(url)
