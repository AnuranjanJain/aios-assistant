import json
from datetime import date, datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.services.analytics import analytics_report
from app.services.knowledge_graph import build_knowledge_graph


QUESTION_INTENTS = {
    "genai_video": ["genai video", "video should i watch", "watch next"],
    "hackathon_focus": ["hackathon", "today's focus"],
    "internship_deadline": ["internship deadline", "closest internship"],
    "email_replies": ["emails need replies", "email need replies", "reply", "replies"],
    "finish_before": ["finish before", "before friday", "can i finish"],
    "work_left": ["work left", "how much work"],
    "risk": ["risk", "at risk"],
    "forgetting": ["forgetting", "forgot", "miss"],
    "now": ["what should i do now", "do now", "next"],
}


def answer_executive_question(question, app_config=None):
    question = (question or "").strip()
    graph = build_knowledge_graph()
    context = build_executive_context(graph)
    intent = detect_intent(question)
    answer = rule_based_answer(question, intent, context)
    config = app_config or {}
    ollama_answer = synthesize_with_ollama(question, answer, context, config)
    if ollama_answer:
        answer["answer"] = ollama_answer
        answer["mode"] = f"ollama:{config.get('OLLAMA_MODEL') or 'local'}"
    return answer


def executive_briefing(app_config=None):
    questions = [
        "What should I do now?",
        "What am I forgetting?",
        "What projects are at risk?",
        "Which internship deadline is closest?",
        "What emails need replies?",
        "How much work is left?",
        "Can I finish before Friday?",
        "Which GenAI video should I watch next?",
        "What hackathon deserves today's focus?",
    ]
    return {
        "ok": True,
        "assistant": [answer_executive_question(question, app_config) for question in questions],
    }


def build_executive_context(graph):
    nodes = list(graph["nodes"].values())
    edges = graph["edges"]
    buckets = {}
    for node in nodes:
        buckets.setdefault(node["kind"], []).append(node)
    today = date.today()
    return {
        "graph": {"nodes": len(nodes), "edges": len(edges), "kinds": sorted(buckets)},
        "analytics": analytics_report("weekly", today),
        "life_items": buckets.get("life_item", []),
        "projects": buckets.get("project", []) + buckets.get("repository", []) + buckets.get("goal", []),
        "milestones": buckets.get("milestone", []),
        "emails": buckets.get("email", []),
        "hackathons": buckets.get("hackathon", []),
        "learning": buckets.get("learning", []),
        "meetings": buckets.get("meeting", []) + buckets.get("calendar", []),
        "notes": buckets.get("note", []),
        "people": buckets.get("person", []),
        "companies": buckets.get("company", []),
    }


def detect_intent(question):
    lowered = question.lower()
    for intent, phrases in QUESTION_INTENTS.items():
        if any(phrase in lowered for phrase in phrases):
            return intent
    return "now"


def rule_based_answer(question, intent, context):
    handlers = {
        "now": answer_now,
        "forgetting": answer_forgetting,
        "risk": answer_risk,
        "internship_deadline": answer_internship_deadline,
        "email_replies": answer_email_replies,
        "work_left": answer_work_left,
        "finish_before": answer_finish_before,
        "genai_video": answer_genai_video,
        "hackathon_focus": answer_hackathon_focus,
    }
    payload = handlers.get(intent, answer_now)(context, question)
    payload.update(
        {
            "ok": True,
            "query": question,
            "intent": intent,
            "mode": "rule_based_graph",
            "graph_used": True,
            "graph_scope": context["graph"],
            "evidence_domains": evidence_domains(context),
        }
    )
    return payload


def answer_now(context, _question):
    candidates = active_work_items(context)
    choice = first(candidates) or first(context["hackathons"]) or first(context["learning"])
    title = node_title(choice) if choice else "Start with a short planning review."
    action = node_action(choice) if choice else "Open the planning board and pick one concrete task."
    answer = f"Do now: {title}. Next action: {action}"
    return {"answer": answer, "primary": compact_node(choice), "recommendations": compact_nodes(candidates, 5)}


def answer_forgetting(context, _question):
    due = due_or_blocked_nodes(context)
    stale_emails = email_reply_nodes(context)
    learning = stale_learning_nodes(context)
    items = due[:4] + stale_emails[:3] + learning[:3]
    if not items:
        answer = "I do not see an obvious forgotten item in the graph right now."
    else:
        answer = "You may be forgetting: " + "; ".join(node_title(item) for item in items[:5])
    return {"answer": answer, "items": compact_nodes(items, 10)}


def answer_risk(context, _question):
    risky = risky_projects(context)
    answer = "Projects at risk: " + "; ".join(node_title(item) for item in risky[:5]) if risky else "No high-risk project stands out from the graph."
    return {"answer": answer, "projects": compact_nodes(risky, 10)}


def answer_internship_deadline(context, _question):
    nodes = [
        node
        for node in context["life_items"] + context["emails"] + context["milestones"]
        if "intern" in searchable_text(node)
    ]
    nodes = sorted([node for node in nodes if parse_datetime(node.get("data", {}).get("deadline"))], key=lambda item: parse_datetime(item["data"]["deadline"]))
    if not nodes:
        return {"answer": "I do not see an internship deadline in the graph yet.", "deadline": None}
    node = nodes[0]
    return {
        "answer": f"Closest internship deadline: {node_title(node)} on {node['data']['deadline']}.",
        "deadline": compact_node(node),
    }


def answer_email_replies(context, _question):
    emails = email_reply_nodes(context)
    answer = "Emails needing replies: " + "; ".join(node_title(item) for item in emails[:5]) if emails else "No reply-needed emails are visible in the graph."
    return {"answer": answer, "emails": compact_nodes(emails, 10)}


def answer_work_left(context, _question):
    work = active_work_items(context)
    minutes = sum(int((node.get("data") or {}).get("planned_minutes") or 0) for node in context["milestones"])
    answer = f"Open work left: {len(work)} connected items"
    if minutes:
        answer += f", about {round(minutes / 60, 1)} planned hours"
    answer += "."
    return {"answer": answer, "open_items": compact_nodes(work, 12), "planned_hours": round(minutes / 60, 2)}


def answer_finish_before(context, question):
    target = parse_finish_target(question) or next_weekday(date.today(), 4)
    work = active_work_items(context)
    planned_minutes = sum(int((node.get("data") or {}).get("planned_minutes") or 45) for node in work if node["kind"] == "milestone")
    if planned_minutes == 0:
        planned_minutes = len(work) * 45
    available_days = max(1, (target - date.today()).days + 1)
    capacity_minutes = available_days * 5 * 60
    can_finish = planned_minutes <= capacity_minutes
    answer = (
        f"Yes, likely before {target.isoformat()} if you protect about {round(planned_minutes / 60, 1)}h."
        if can_finish
        else f"Risky before {target.isoformat()}: visible work is about {round(planned_minutes / 60, 1)}h against {round(capacity_minutes / 60, 1)}h practical capacity."
    )
    return {"answer": answer, "can_finish": can_finish, "target_date": target.isoformat(), "visible_work_hours": round(planned_minutes / 60, 2)}


def answer_genai_video(context, _question):
    videos = [
        node
        for node in context["learning"] + context["milestones"]
        if any(term in searchable_text(node) for term in ["genai", "generative ai", "llm", "attention", "transformer", "video"])
    ]
    videos.sort(key=lambda node: (completion(node), parse_datetime((node.get("data") or {}).get("next_revision_at")) or datetime.max))
    if not videos:
        return {"answer": "I do not see a GenAI video queued in the graph.", "video": None}
    video = videos[0]
    return {"answer": f"Watch next: {node_title(video)}.", "video": compact_node(video)}


def answer_hackathon_focus(context, _question):
    hackathons = sorted(context["hackathons"], key=hackathon_priority)
    if not hackathons:
        return {"answer": "No active hackathon is visible in the graph.", "hackathon": None}
    item = hackathons[0]
    deadline = (item.get("data") or {}).get("deadline")
    suffix = f" Deadline: {deadline}." if deadline else ""
    return {
        "answer": f"Today's hackathon focus: {node_title(item)}.{suffix} Next action: {node_action(item)}",
        "hackathon": compact_node(item),
    }


def active_work_items(context):
    nodes = context["life_items"] + context["milestones"] + context["projects"] + context["hackathons"] + context["learning"]
    active = [node for node in nodes if status(node) not in {"completed", "done", "cancelled", "archived"}]
    active.sort(key=priority_key)
    return active


def due_or_blocked_nodes(context):
    nodes = context["life_items"] + context["milestones"] + context["meetings"] + context["hackathons"] + context["learning"]
    return [node for node in sorted(nodes, key=priority_key) if status(node) == "blocked" or is_due_soon(node)]


def risky_projects(context):
    projects = context["projects"] + context["life_items"] + context["hackathons"]
    return [
        node
        for node in sorted(projects, key=priority_key)
        if (node.get("data") or {}).get("inactive")
        or status(node) == "blocked"
        or is_due_soon(node)
        or "risk" in searchable_text(node)
    ]


def email_reply_nodes(context):
    emails = []
    for node in context["emails"]:
        data = node.get("data") or {}
        text = searchable_text(node)
        if data.get("priority") == "high" or "reply" in text or "follow" in text or data.get("actions"):
            emails.append(node)
    emails.sort(key=priority_key)
    return emails


def stale_learning_nodes(context):
    return [node for node in context["learning"] if completion(node) < 1.0]


def evidence_domains(context):
    domains = []
    mapping = {
        "life_items": "life_items",
        "projects": "projects_repositories_goals",
        "emails": "emails",
        "hackathons": "hackathons",
        "learning": "learning",
        "meetings": "meetings_calendar",
        "notes": "notes_memory",
    }
    for key, label in mapping.items():
        if context.get(key):
            domains.append(label)
    domains.append("analytics")
    return domains


def synthesize_with_ollama(question, answer, context, config):
    if config.get("AI_PROVIDER") != "ollama":
        return ""
    base_url = str(config.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    if not is_loopback_url(base_url):
        return ""
    payload = {
        "model": config.get("OLLAMA_MODEL") or "qwen2.5:3b",
        "prompt": (
            "You are a local AI executive assistant. Use only this local graph-derived context. "
            "Answer in 2 concise sentences, with one clear next action. "
            f"Question: {question}\n"
            f"Draft: {answer.get('answer')}\n"
            f"Evidence domains: {', '.join(answer.get('evidence_domains', []))}\n"
            f"Graph scope: {json.dumps(context.get('graph', {}))}\n"
            f"Top evidence: {json.dumps(answer, default=str)[:4000]}"
        ),
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        request = Request(
            f"{base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        return str(result.get("response") or "").strip()
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return ""


def priority_key(node):
    data = node.get("data") or {}
    priority_rank = {"urgent": 0, "high": 1, "normal": 2, "medium": 2, "low": 3}.get(str(data.get("priority") or "normal").lower(), 2)
    deadline = parse_datetime(data.get("deadline")) or parse_datetime(data.get("planned_start")) or datetime.max
    inactive = 0 if data.get("inactive") else 1
    blocked = 0 if status(node) == "blocked" else 1
    return (blocked, inactive, deadline, priority_rank, node_title(node))


def hackathon_priority(node):
    data = node.get("data") or {}
    deadline = parse_datetime(data.get("deadline")) or datetime.max
    status_penalty = 0 if str(data.get("status") or "").lower() in {"applied", "shortlisted", "deadline", "submission due"} else 1
    return (deadline, status_penalty, node_title(node))


def is_due_soon(node):
    deadline = parse_datetime((node.get("data") or {}).get("deadline"))
    return bool(deadline and deadline.date() <= date.today() + timedelta(days=7))


def status(node):
    return str((node.get("data") or {}).get("status") or "").lower()


def completion(node):
    try:
        return float((node.get("data") or {}).get("completion") or (node.get("data") or {}).get("progress") or 0)
    except (TypeError, ValueError):
        return 0.0


def node_title(node):
    return (node or {}).get("title") or "Untitled"


def node_action(node):
    data = (node or {}).get("data") or {}
    return data.get("next_action") or data.get("remaining_work") or data.get("summary") or "Choose the next concrete action."


def compact_node(node):
    if not node:
        return None
    return {"id": node["id"], "kind": node["kind"], "title": node["title"], "data": node.get("data", {})}


def compact_nodes(nodes, limit):
    return [compact_node(node) for node in nodes[:limit]]


def searchable_text(node):
    data = node.get("data") or {}
    values = [node.get("title", "")]
    for value in data.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values())
        else:
            values.append(str(value))
    return " ".join(values).lower()


def parse_finish_target(question):
    lowered = question.lower()
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, index in weekdays.items():
        if name in lowered:
            return next_weekday(date.today(), index)
    return None


def next_weekday(anchor, weekday):
    days = (weekday - anchor.weekday()) % 7
    return anchor + timedelta(days=days)


def first(items):
    return items[0] if items else None


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def is_loopback_url(value):
    host = urlsplit(value).hostname
    return host in {"localhost", "127.0.0.1", "::1"}
