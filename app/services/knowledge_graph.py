import json
import re
from collections import deque

from app.models import (
    EmailInsight,
    GitHubRepository,
    GoalPlan,
    LearningItem,
    LifeItem,
    LifeItemRelation,
    MemoryEntity,
    MemoryFact,
    MemoryRelation,
    Opportunity,
    PlanTask,
    PlanningEvent,
    WorkCheckpoint,
)


def _json(value, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def terms(value):
    return set(re.findall(r"[a-z0-9]{2,}", str(value or "").lower()))


def node_id(kind, identifier):
    return f"{kind}:{identifier}"


def add_node(graph, kind, identifier, title, **data):
    ident = node_id(kind, identifier)
    node = graph["nodes"].setdefault(
        ident,
        {
            "id": ident,
            "kind": kind,
            "title": str(title or ident),
            "data": {},
        },
    )
    node["data"].update({key: value for key, value in data.items() if value not in (None, "", [])})
    return ident


def add_edge(graph, source, target, relation, **data):
    if not source or not target or source == target:
        return
    edge_key = (source, target, relation)
    if edge_key in graph["edge_keys"]:
        return
    graph["edge_keys"].add(edge_key)
    graph["edges"].append(
        {
            "source": source,
            "target": target,
            "relation": relation,
            "data": {key: value for key, value in data.items() if value not in (None, "", [])},
        }
    )


def build_knowledge_graph():
    graph = {"nodes": {}, "edges": [], "edge_keys": set()}
    life_nodes = {}

    for item in LifeItem.query.limit(500).all():
        life_nodes[item.id] = add_node(
            graph,
            "life_item",
            item.id,
            item.title,
            category=item.category,
            status=item.status,
            priority=item.priority,
            deadline=item.deadline.isoformat() if item.deadline else None,
            progress=item.progress,
            repository=item.repository,
            summary=item.ai_summary or item.description,
            next_action=item.next_action,
            tags=_json(item.tags_json),
            metadata=_json(item.metadata_json, {}),
        )

    for relation in LifeItemRelation.query.limit(1000).all():
        add_edge(
            graph,
            life_nodes.get(relation.source_item_id),
            life_nodes.get(relation.target_item_id),
            relation.relation_type,
            strength=relation.strength,
            reason=relation.reason,
            metadata=_json(relation.metadata_json, {}),
        )

    connect_emails(graph, life_nodes)
    connect_hackathons(graph)
    connect_repositories(graph, life_nodes)
    connect_learning(graph, life_nodes)
    connect_planning(graph, life_nodes)
    connect_memory(graph)
    connect_goal_plans(graph)
    connect_by_shared_terms(graph)

    graph["edge_keys"] = None
    return graph


def connect_emails(graph, life_nodes):
    for insight in EmailInsight.query.order_by(EmailInsight.updated_at.desc()).limit(300).all():
        email = insight.email
        title = email.subject if email else insight.summary or f"Email {insight.id}"
        email_id = add_node(
            graph,
            "email",
            insight.id,
            title,
            sender=email.sender if email else "",
            category=insight.category,
            priority=insight.priority,
            summary=insight.summary,
            deadlines=_json(insight.deadlines_json),
            meetings=_json(insight.meetings_json),
            people=_json(insight.people_json),
            companies=_json(insight.companies_json),
            projects=_json(insight.projects_json),
            actions=_json(insight.suggested_actions_json) or _json(insight.action_items_json),
        )
        add_edge(graph, email_id, life_nodes.get(insight.life_item_id), "creates_life_item")
        for person in _json(insight.people_json):
            person_id = add_node(graph, "person", person, person)
            add_edge(graph, email_id, person_id, "mentions_person")
        for company in _json(insight.companies_json):
            company_id = add_node(graph, "company", company, company)
            add_edge(graph, email_id, company_id, "mentions_company")
        for meeting in _json(insight.meetings_json):
            meeting_id = add_node(graph, "meeting", f"{insight.id}:{meeting}", meeting, source="email")
            add_edge(graph, email_id, meeting_id, "mentions_meeting")


def connect_hackathons(graph):
    for item in Opportunity.query.filter_by(kind="hackathon").order_by(Opportunity.updated_at.desc()).limit(200).all():
        hackathon_id = add_node(
            graph,
            "hackathon",
            item.id,
            item.title,
            organization=item.organization,
            status=item.status,
            source=item.source,
            deadline=item.deadline.isoformat() if item.deadline else None,
            notes=item.notes,
            next_action=f"Review hackathon milestone for {item.title}.",
        )
        if item.organization:
            company_id = add_node(graph, "company", item.organization, item.organization)
            add_edge(graph, hackathon_id, company_id, "hosted_by")
        project_id = add_node(graph, "project", item.title, item.title)
        add_edge(graph, hackathon_id, project_id, "creates_project")


def connect_repositories(graph, life_nodes):
    for repo in GitHubRepository.query.order_by(GitHubRepository.updated_at.desc()).limit(200).all():
        repo_id = add_node(
            graph,
            "repository",
            repo.id,
            repo.repo_full_name,
            url=repo.html_url,
            latest_commits=_json(repo.commits_json)[:5],
            current_milestone=repo.current_sprint,
            remaining_work=repo.remaining_work,
            recent_progress=repo.recent_progress,
            next_action=repo.suggested_next_task,
            completion_percentage=repo.completion_percentage,
            inactive=repo.inactive,
        )
        add_edge(graph, repo_id, life_nodes.get(repo.life_item_id), "tracks_life_item")
        for commit in _json(repo.commits_json)[:5]:
            commit_id = add_node(graph, "commit", f"{repo.id}:{commit.get('sha')}", commit.get("message"), date=commit.get("date"), url=commit.get("url"))
            add_edge(graph, repo_id, commit_id, "has_commit")
        for issue in _json(repo.issues_json)[:8]:
            issue_id = add_node(graph, "milestone", f"issue:{repo.id}:{issue.get('number')}", issue.get("title"), status=issue.get("state"), url=issue.get("url"))
            add_edge(graph, repo_id, issue_id, "has_issue")
        for pr in _json(repo.pull_requests_json)[:8]:
            pr_id = add_node(graph, "milestone", f"pr:{repo.id}:{pr.get('number')}", pr.get("title"), status=pr.get("state"), url=pr.get("url"))
            add_edge(graph, repo_id, pr_id, "has_pull_request")


def connect_learning(graph, life_nodes):
    for item in LearningItem.query.order_by(LearningItem.updated_at.desc()).limit(200).all():
        learning_id = add_node(
            graph,
            "learning",
            item.id,
            item.title,
            item_type=item.item_type,
            completion=item.completion,
            notes=item.notes,
            weak_topics=_json(item.weak_topics_json),
            projects=_json(item.projects_json),
            next_revision_at=item.next_revision_at.isoformat() if item.next_revision_at else None,
        )
        add_edge(graph, learning_id, life_nodes.get(item.life_item_id), "tracks_life_item")
        for project in _json(item.projects_json) + ([item.project] if item.project else []):
            project_id = add_node(graph, "project", project, project)
            add_edge(graph, learning_id, project_id, "supports_project")


def connect_planning(graph, life_nodes):
    for event in PlanningEvent.query.order_by(PlanningEvent.updated_at.desc()).limit(300).all():
        metadata = _json(event.metadata_json, {})
        kind = "meeting" if event.event_type == "meeting" else "calendar" if event.source == "calendar" else "milestone"
        event_id = add_node(
            graph,
            kind,
            event.id,
            event.title,
            event_type=event.event_type,
            source=event.source,
            project=event.project,
            deadline=event.deadline.isoformat() if event.deadline else None,
            planned_start=event.planned_start.isoformat() if event.planned_start else None,
            status=event.status,
            priority=event.priority,
            notes=event.idea,
            work_done=event.work_done,
            remaining_work=event.work_left,
            next_action=event.next_question,
            history=metadata.get("progress_log") or metadata.get("assistant_history"),
        )
        if metadata.get("learning_item_id"):
            add_edge(graph, event_id, node_id("learning", metadata["learning_item_id"]), "plans_learning")
        if event.repo_url:
            repo = GitHubRepository.query.filter(GitHubRepository.html_url.like(f"%{event.repo_url.split('github.com/')[-1]}%")).first()
            if repo:
                add_edge(graph, event_id, node_id("repository", repo.id), "plans_repository")
        if event.project:
            project_id = add_node(graph, "project", event.project, event.project)
            add_edge(graph, event_id, project_id, "belongs_to_project")


def connect_memory(graph):
    memory_nodes = {}
    for entity in MemoryEntity.query.limit(300).all():
        memory_nodes[entity.id] = add_node(
            graph,
            entity.entity_type,
            f"memory:{entity.id}",
            entity.name,
            status=entity.status,
            summary=entity.summary,
            metadata=_json(entity.metadata_json, {}),
        )
    for relation in MemoryRelation.query.limit(800).all():
        add_edge(graph, memory_nodes.get(relation.source_id), memory_nodes.get(relation.target_id), relation.relation_type)
    for fact in MemoryFact.query.order_by(MemoryFact.created_at.desc()).limit(300).all():
        note_id = add_node(graph, "note", fact.id, fact.content[:80], content=fact.content, fact_type=fact.fact_type, source=fact.source)
        add_edge(graph, memory_nodes.get(fact.entity_id), note_id, "has_note")
    for checkpoint in WorkCheckpoint.query.order_by(WorkCheckpoint.created_at.desc()).limit(200).all():
        note_id = add_node(
            graph,
            "note",
            f"checkpoint:{checkpoint.id}",
            checkpoint.summary or checkpoint.notes or f"Checkpoint {checkpoint.id}",
            summary=checkpoint.summary,
            notes=checkpoint.notes,
            active_tasks=_json(checkpoint.active_tasks_json),
            next_actions=_json(checkpoint.next_actions_json),
        )
        add_edge(graph, memory_nodes.get(checkpoint.project_id), note_id, "has_checkpoint")


def connect_goal_plans(graph):
    for plan in GoalPlan.query.order_by(GoalPlan.updated_at.desc()).limit(100).all():
        goal_id = node_id("goal", f"memory:{plan.goal_id}")
        plan_id = add_node(graph, "goal", f"plan:{plan.id}", plan.title, status=plan.status, strategy=plan.strategy)
        add_edge(graph, goal_id, plan_id, "has_plan")
        for task in plan.tasks:
            task_id = add_node(
                graph,
                "milestone",
                f"plan_task:{task.id}",
                task.title,
                status=task.status,
                description=task.description,
                remaining_work=task.suggested_next,
                resources=_json(task.resources_json),
            )
            add_edge(graph, plan_id, task_id, "has_milestone")


def connect_by_shared_terms(graph):
    nodes = list(graph["nodes"].values())
    projectish = [node for node in nodes if node["kind"] in {"life_item", "project", "repository", "goal"}]
    others = [node for node in nodes if node["kind"] not in {"commit"}]
    for source in projectish:
        source_terms = searchable_terms(source)
        if not source_terms:
            continue
        for target in others:
            if source["id"] == target["id"]:
                continue
            overlap = source_terms & searchable_terms(target)
            if len(overlap) >= 1 and strong_overlap(overlap, source, target):
                add_edge(graph, source["id"], target["id"], "shared_context", signals=sorted(overlap)[:5])


def searchable_terms(node):
    data = node.get("data") or {}
    chunks = [node.get("title", "")]
    for key in ["project", "summary", "notes", "remaining_work", "next_action", "current_milestone", "repository"]:
        chunks.append(data.get(key, ""))
    for key in ["tags", "projects", "companies", "people", "weak_topics"]:
        chunks.extend(data.get(key) or [])
    return {term for term in terms(" ".join(str(chunk) for chunk in chunks)) if term not in STOP_TERMS}


STOP_TERMS = {"the", "and", "for", "with", "this", "that", "work", "next", "task", "project", "notes", "email"}


def strong_overlap(overlap, source, target):
    if len(overlap) >= 2:
        return True
    signal = next(iter(overlap))
    return len(signal) >= 5 and signal in terms(source.get("title", "")) | terms(target.get("title", ""))


def query_knowledge_graph(query, max_depth=2):
    graph = build_knowledge_graph()
    matches = find_matching_nodes(graph, query)
    visited, edges = traverse(graph, [node["id"] for node in matches], max_depth=max_depth)
    subgraph_nodes = [graph["nodes"][identifier] for identifier in visited]
    answer = synthesize_answer(query, matches, subgraph_nodes, edges)
    return {
        "query": query,
        "matches": matches[:10],
        "answer": answer,
        "nodes": sorted(subgraph_nodes, key=lambda item: (node_rank(item), item["title"]))[:80],
        "edges": edges[:160],
    }


def find_matching_nodes(graph, query):
    query_terms = terms(query)
    scored = []
    for node in graph["nodes"].values():
        haystack = searchable_terms(node) | terms(node.get("title", ""))
        score = len(query_terms & haystack)
        if str(query or "").lower() in node.get("title", "").lower():
            score += 4
        if "continue" in query_terms and node["kind"] in {"life_item", "project", "repository", "goal"}:
            score += 1
        if score:
            scored.append((score, node))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [node for _score, node in scored[:12]]


def traverse(graph, start_ids, max_depth=2):
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append((edge, edge["target"]))
        adjacency.setdefault(edge["target"], []).append((edge, edge["source"]))
    visited = set(start_ids)
    found_edges = []
    queue = deque((identifier, 0) for identifier in start_ids)
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge, neighbor in adjacency.get(current, []):
            found_edges.append(edge)
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return visited, dedupe_edges(found_edges)


def dedupe_edges(edges):
    seen = set()
    result = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["relation"])
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def synthesize_answer(query, matches, nodes, edges):
    buckets = {}
    for node in nodes:
        buckets.setdefault(node["kind"], []).append(node)
    repos = buckets.get("repository", [])
    milestones = buckets.get("milestone", [])
    emails = buckets.get("email", [])
    learning = buckets.get("learning", [])
    notes = buckets.get("note", [])
    meetings = buckets.get("meeting", []) + buckets.get("calendar", [])
    life_items = buckets.get("life_item", [])

    latest_commits = []
    for repo in repos:
        latest_commits.extend((repo["data"].get("latest_commits") or [])[:3])
    deadlines = [
        {"title": node["title"], "deadline": node["data"].get("deadline")}
        for node in nodes
        if node["data"].get("deadline")
    ]
    remaining = first_present(
        [repo["data"].get("remaining_work") for repo in repos]
        + [node["data"].get("remaining_work") for node in milestones]
        + [item["data"].get("next_action") for item in life_items]
    )
    next_action = first_present(
        [repo["data"].get("next_action") for repo in repos]
        + [node["data"].get("next_action") for node in life_items]
        + [node["data"].get("remaining_work") for node in milestones]
    )
    return {
        "summary": f"Found {len(nodes)} connected graph nodes for '{query}'.",
        "latest_commits": latest_commits[:5],
        "current_milestone": first_present([repo["data"].get("current_milestone") for repo in repos] + [node["title"] for node in milestones]),
        "emails": compact_nodes(emails, 6),
        "notes": compact_nodes(notes, 6),
        "deadlines": deadlines[:8],
        "remaining_work": remaining,
        "related_learning": compact_nodes(learning, 6),
        "meetings": compact_nodes(meetings, 6),
        "people": compact_nodes(buckets.get("person", []), 8),
        "companies": compact_nodes(buckets.get("company", []), 8),
        "goals": compact_nodes(buckets.get("goal", []), 6),
        "next_action": next_action or "Review the connected graph nodes and choose the next concrete task.",
        "paths": [{"from": edge["source"], "to": edge["target"], "relation": edge["relation"]} for edge in edges[:12]],
    }


def first_present(values):
    for value in values:
        if value:
            return value
    return ""


def compact_nodes(nodes, limit):
    return [{"id": node["id"], "title": node["title"], "kind": node["kind"], "data": node.get("data", {})} for node in nodes[:limit]]


def node_rank(node):
    return {
        "life_item": 0,
        "repository": 1,
        "milestone": 2,
        "email": 3,
        "learning": 4,
        "meeting": 5,
        "calendar": 6,
        "note": 7,
    }.get(node["kind"], 9)
