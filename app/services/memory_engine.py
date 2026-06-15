import json
import math
import re
from datetime import datetime, time, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.models import MemoryEntity, MemoryFact, MemoryRelation, WorkCheckpoint, db
from app.services.vector_store import rank_vectors


ENTITY_TYPES = {
    "user",
    "preference",
    "project",
    "goal",
    "skill",
    "job_application",
    "learning_path",
    "recurring_task",
}
OPEN_STATUSES = {"active", "planned", "paused", "blocked", "in_progress"}
USER_RELATIONS = {
    "project": "owns_project",
    "goal": "pursues_goal",
    "skill": "has_skill",
    "job_application": "applied_to",
    "learning_path": "follows_learning_path",
    "preference": "has_preference",
    "recurring_task": "repeats_task",
}


def slugify(value):
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return cleaned[:180] or "memory"


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[\n,]+", str(value or "")) if item.strip()]


def upsert_entity(data):
    entity_type = str(data.get("entity_type") or data.get("type") or "project").strip().lower()
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unsupported entity type: {entity_type}")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    slug = str(data.get("slug") or f"{entity_type}-{slugify(name)}").strip().lower()
    entity = MemoryEntity.query.filter_by(slug=slug).first()
    if entity is None:
        entity = MemoryEntity(entity_type=entity_type, name=name, slug=slug)
        db.session.add(entity)

    entity.entity_type = entity_type
    entity.name = name[:180]
    entity.status = str(data.get("status") or entity.status or "active").strip().lower()[:60]
    entity.summary = str(data.get("summary") or entity.summary or "").strip()
    entity.last_worked_at = parse_datetime(data.get("last_worked_at")) or entity.last_worked_at
    if "metadata" in data:
        entity.metadata_json = json.dumps(data.get("metadata") or {}, ensure_ascii=True)
    db.session.flush()
    link_entity_to_user(entity)
    return entity


def ensure_user_entity(name):
    user = MemoryEntity.query.filter_by(entity_type="user").order_by(MemoryEntity.id.asc()).first()
    if user is None:
        user = MemoryEntity(
            entity_type="user",
            name=str(name or "Local User").strip()[:180],
            slug="user-local",
            status="active",
            summary="Owner of this local-first personal memory.",
        )
        db.session.add(user)
        db.session.flush()
    elif name and user.name == "Local User":
        user.name = str(name).strip()[:180]
    return user


def link_entity_to_user(entity):
    if entity.entity_type == "user":
        return
    user = MemoryEntity.query.filter_by(entity_type="user").order_by(MemoryEntity.id.asc()).first()
    if user is None:
        return
    relation_type = USER_RELATIONS.get(entity.entity_type, "remembers")
    existing = MemoryRelation.query.filter_by(
        source_id=user.id,
        target_id=entity.id,
        relation_type=relation_type,
    ).first()
    if existing is None:
        db.session.add(
            MemoryRelation(
                source=user,
                target=entity,
                relation_type=relation_type,
            )
        )


def remember(data, config):
    entity = None
    entity_id = data.get("entity_id")
    if entity_id:
        entity = db.session.get(MemoryEntity, int(entity_id))
    elif data.get("entity") or data.get("entity_name"):
        entity_data = data.get("entity") if isinstance(data.get("entity"), dict) else {
            "name": data.get("entity_name"),
            "entity_type": data.get("entity_type", "project"),
        }
        entity = upsert_entity(entity_data)

    content = str(data.get("content") or data.get("note") or "").strip()
    if not content:
        raise ValueError("content is required")

    fact = MemoryFact(
        entity=entity,
        fact_type=str(data.get("fact_type") or "note").strip().lower()[:50],
        content=content,
        source=str(data.get("source") or "manual").strip()[:120],
        importance=max(0.0, min(1.0, float(data.get("importance") or 0.5))),
        occurred_at=parse_datetime(data.get("occurred_at")) or datetime.utcnow(),
    )
    fact.embedding_json = encode_embedding(embed_text(memory_text(fact, entity), config))
    db.session.add(fact)
    return fact


def save_checkpoint(data, config):
    project_data = data.get("project") if isinstance(data.get("project"), dict) else {
        "name": data.get("project_name"),
        "entity_type": "project",
        "status": data.get("status", "active"),
        "summary": data.get("project_summary", ""),
    }
    project_data["entity_type"] = "project"
    project = upsert_entity(project_data)
    project.last_worked_at = parse_datetime(data.get("worked_at")) or datetime.utcnow()

    checkpoint = WorkCheckpoint(
        project=project,
        summary=str(data.get("summary") or "").strip(),
        open_files_json=json.dumps(parse_list(data.get("open_files")), ensure_ascii=True),
        active_tasks_json=json.dumps(parse_list(data.get("active_tasks")), ensure_ascii=True),
        next_actions_json=json.dumps(parse_list(data.get("next_actions")), ensure_ascii=True),
        notes=str(data.get("notes") or "").strip(),
        source=str(data.get("source") or "manual").strip()[:120],
    )
    db.session.add(checkpoint)
    db.session.flush()

    searchable = " ".join(
        [
            project.name,
            checkpoint.summary or "",
            checkpoint.notes or "",
            " ".join(parse_json_list(checkpoint.active_tasks_json)),
            " ".join(parse_json_list(checkpoint.next_actions_json)),
            " ".join(parse_json_list(checkpoint.open_files_json)),
        ]
    )
    db.session.add(
        MemoryFact(
            entity=project,
            fact_type="checkpoint",
            content=searchable.strip(),
            source=checkpoint.source,
            importance=0.9,
            occurred_at=project.last_worked_at,
            embedding_json=encode_embedding(embed_text(searchable, config)),
        )
    )
    return checkpoint


def relate_entities(data):
    source = resolve_entity(data.get("source_id"), data.get("source"))
    target = resolve_entity(data.get("target_id"), data.get("target"))
    if source is None or target is None:
        raise ValueError("source and target entities are required")
    if source.id == target.id:
        raise ValueError("an entity cannot relate to itself")

    relation_type = str(data.get("relation_type") or "related_to").strip().lower()[:60]
    relation = MemoryRelation.query.filter_by(
        source_id=source.id,
        target_id=target.id,
        relation_type=relation_type,
    ).first()
    if relation is None:
        relation = MemoryRelation(source=source, target=target, relation_type=relation_type)
        db.session.add(relation)
    return relation


def search_memory(query, config, limit=10):
    query = str(query or "").strip()
    if not query:
        return []

    intent_results = search_by_intent(query, limit)
    query_embedding = embed_text(query, config)
    terms = set(re.findall(r"[a-z0-9]{2,}", query.lower()))
    scored = {}
    facts = MemoryFact.query.order_by(MemoryFact.created_at.desc()).limit(500).all()
    vector_scores = rank_vectors(
        query_embedding,
        facts,
        backend=config.get("MEMORY_VECTOR_BACKEND", "auto"),
        storage_path=config.get("MEMORY_VECTOR_PATH", "instance/memory_vectors"),
    )

    for fact in facts:
        text = memory_text(fact, fact.entity)
        lexical = lexical_score(terms, text)
        semantic = vector_scores.get(fact.id, 0.0)
        recency = recency_score(fact.occurred_at or fact.created_at)
        score = lexical * 0.5 + semantic * 0.4 + recency * 0.1 + fact.importance * 0.05
        if score > 0.05:
            scored[f"fact:{fact.id}"] = {
                "kind": "fact",
                "score": round(score, 4),
                "fact": serialize_fact(fact),
                "entity": serialize_entity(fact.entity, include_checkpoint=True) if fact.entity else None,
            }

    combined = intent_results + list(scored.values())
    deduped = {}
    for item in combined:
        key = result_key(item)
        if key not in deduped or item.get("score", 0) > deduped[key].get("score", 0):
            deduped[key] = item
    return sorted(deduped.values(), key=lambda item: item.get("score", 0), reverse=True)[:limit]


def answer_memory_question(query, config):
    results = search_memory(query, config, limit=8)
    lowered = str(query or "").lower()
    if not results:
        return {
            "answer": "I could not find a matching memory yet.",
            "results": [],
            "suggestion": "Save a project checkpoint or memory note first.",
        }

    if "unfinished" in lowered or "open project" in lowered:
        names = [item["entity"]["name"] for item in results if item.get("entity")]
        answer = f"Unfinished projects: {', '.join(dict.fromkeys(names))}." if names else "No unfinished projects found."
    elif "next step" in lowered or "next action" in lowered:
        entity = next((item.get("entity") for item in results if item.get("entity")), None)
        actions = (entity or {}).get("latest_checkpoint", {}).get("next_actions", [])
        answer = f"Next for {entity['name']}: {', '.join(actions)}." if entity and actions else results[0]["fact"]["content"]
    elif "yesterday" in lowered:
        names = [item["entity"]["name"] for item in results if item.get("entity")]
        answer = f"Yesterday you worked on: {', '.join(dict.fromkeys(names))}." if names else results[0]["fact"]["content"]
    else:
        answer = results[0].get("fact", {}).get("content") or results[0].get("entity", {}).get("summary")

    return {"answer": answer, "results": results, "suggestion": None}


def search_by_intent(query, limit):
    lowered = query.lower()
    results = []
    entity_query = MemoryEntity.query

    if "unfinished" in lowered or "open project" in lowered:
        entities = entity_query.filter(
            MemoryEntity.entity_type == "project",
            MemoryEntity.status.in_(OPEN_STATUSES),
        ).order_by(MemoryEntity.updated_at.desc()).limit(limit).all()
        return [{"kind": "entity", "score": 1.0, "entity": serialize_entity(item, True)} for item in entities]

    if "yesterday" in lowered:
        yesterday = datetime.now().date() - timedelta(days=1)
        start = datetime.combine(yesterday, time.min)
        end = datetime.combine(yesterday, time.max)
        entities = entity_query.filter(
            MemoryEntity.last_worked_at >= start,
            MemoryEntity.last_worked_at <= end,
        ).order_by(MemoryEntity.last_worked_at.desc()).limit(limit).all()
        return [{"kind": "entity", "score": 1.0, "entity": serialize_entity(item, True)} for item in entities]

    if "next step" in lowered or "next action" in lowered:
        candidates = MemoryEntity.query.filter_by(entity_type="project").all()
        for entity in candidates:
            if entity.name.lower() in lowered:
                return [{"kind": "entity", "score": 1.0, "entity": serialize_entity(entity, True)}]
    return results


def memory_graph():
    entities = MemoryEntity.query.order_by(MemoryEntity.updated_at.desc()).all()
    relations = MemoryRelation.query.order_by(MemoryRelation.created_at.asc()).all()
    return {
        "nodes": [serialize_entity(item, include_checkpoint=False) for item in entities],
        "edges": [serialize_relation(item) for item in relations],
    }


def memory_overview():
    projects = MemoryEntity.query.filter_by(entity_type="project").order_by(MemoryEntity.updated_at.desc()).all()
    entities = MemoryEntity.query.order_by(MemoryEntity.updated_at.desc()).limit(30).all()
    recent_facts = MemoryFact.query.order_by(MemoryFact.created_at.desc()).limit(10).all()
    return {
        "projects": [serialize_entity(item, True) for item in projects],
        "entities": [serialize_entity(item, False) for item in entities],
        "recent_facts": [serialize_fact(item) for item in recent_facts],
        "counts": {
            "entities": MemoryEntity.query.count(),
            "facts": MemoryFact.query.count(),
            "projects": MemoryEntity.query.filter_by(entity_type="project").count(),
            "relations": MemoryRelation.query.count(),
        },
    }


def serialize_entity(entity, include_checkpoint=False):
    if entity is None:
        return None
    payload = {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "slug": entity.slug,
        "status": entity.status,
        "summary": entity.summary or "",
        "metadata": parse_json_object(entity.metadata_json),
        "last_worked_at": entity.last_worked_at.isoformat() if entity.last_worked_at else None,
        "updated_at": entity.updated_at.isoformat(),
    }
    if include_checkpoint:
        latest = (
            WorkCheckpoint.query.filter_by(project_id=entity.id)
            .order_by(WorkCheckpoint.created_at.desc())
            .first()
        )
        payload["latest_checkpoint"] = serialize_checkpoint(latest) if latest else None
    return payload


def serialize_fact(fact):
    return {
        "id": fact.id,
        "entity_id": fact.entity_id,
        "fact_type": fact.fact_type,
        "content": fact.content,
        "source": fact.source,
        "importance": fact.importance,
        "occurred_at": fact.occurred_at.isoformat() if fact.occurred_at else None,
        "created_at": fact.created_at.isoformat(),
    }


def serialize_checkpoint(checkpoint):
    return {
        "id": checkpoint.id,
        "summary": checkpoint.summary or "",
        "open_files": parse_json_list(checkpoint.open_files_json),
        "active_tasks": parse_json_list(checkpoint.active_tasks_json),
        "next_actions": parse_json_list(checkpoint.next_actions_json),
        "notes": checkpoint.notes or "",
        "source": checkpoint.source,
        "created_at": checkpoint.created_at.isoformat(),
    }


def serialize_relation(relation):
    return {
        "id": relation.id,
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "relation_type": relation.relation_type,
    }


def resolve_entity(entity_id, name):
    if entity_id:
        return db.session.get(MemoryEntity, int(entity_id))
    if name:
        lowered = str(name).strip().lower()
        return MemoryEntity.query.filter(db.func.lower(MemoryEntity.name) == lowered).first()
    return None


def memory_text(fact, entity):
    return " ".join(
        part for part in [
            entity.entity_type if entity else "",
            entity.name if entity else "",
            entity.summary if entity else "",
            fact.fact_type,
            fact.content,
        ] if part
    )


def embed_text(text, config):
    text = str(text or "").strip()
    if not text:
        return []
    base_url = str(config.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    model = str(config.get("OLLAMA_EMBED_MODEL") or "nomic-embed-text").strip()
    payload = {"model": model, "input": text[:8000]}
    request = Request(
        f"{base_url}/api/embed",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        embeddings = data.get("embeddings") or []
        return [float(value) for value in embeddings[0]] if embeddings else []
    except (OSError, URLError, ValueError, KeyError, json.JSONDecodeError):
        return []


def lexical_score(terms, text):
    if not terms:
        return 0.0
    lowered = text.lower()
    matched = sum(1 for term in terms if term in lowered)
    return matched / len(terms)


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def recency_score(value):
    if not value:
        return 0.0
    age_days = max(0, (datetime.utcnow() - value).days)
    return 1 / (1 + age_days / 30)


def encode_embedding(values):
    return json.dumps(values) if values else None


def decode_embedding(value):
    try:
        payload = json.loads(value or "[]")
        return [float(item) for item in payload]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def parse_json_list(value):
    try:
        payload = json.loads(value or "[]")
        return payload if isinstance(payload, list) else []
    except json.JSONDecodeError:
        return []


def parse_json_object(value):
    try:
        payload = json.loads(value or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def result_key(item):
    if item.get("entity"):
        return f"entity:{item['entity']['id']}"
    return f"fact:{item.get('fact', {}).get('id')}"
