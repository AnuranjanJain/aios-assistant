import json
import math
from pathlib import Path


def rank_vectors(query_embedding, facts, backend="auto", storage_path="instance/memory_vectors", limit=25):
    rows = [(fact.id, decode_vector(fact.embedding_json)) for fact in facts]
    rows = [
        (fact_id, vector)
        for fact_id, vector in rows
        if vector and len(vector) == len(query_embedding)
    ]
    if not query_embedding or not rows:
        return {}

    selected = str(backend or "auto").lower()
    if selected in {"auto", "chroma"}:
        try:
            ranked = rank_with_chroma(query_embedding, rows, storage_path, limit)
        except Exception:
            ranked = None
        if ranked is not None:
            return ranked
    if selected in {"auto", "faiss"}:
        try:
            ranked = rank_with_faiss(query_embedding, rows, limit)
        except Exception:
            ranked = None
        if ranked is not None:
            return ranked
    return rank_with_python(query_embedding, rows)


def rank_with_chroma(query_embedding, rows, storage_path, limit):
    try:
        import chromadb
    except ImportError:
        return None

    path = Path(storage_path)
    path.mkdir(parents=True, exist_ok=True)
    collection = chromadb.PersistentClient(path=str(path)).get_or_create_collection(
        "aios_memory",
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(
        ids=[str(fact_id) for fact_id, _vector in rows],
        embeddings=[vector for _fact_id, vector in rows],
    )
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit, len(rows)),
        include=["distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return {int(fact_id): max(0.0, 1.0 - float(distance)) for fact_id, distance in zip(ids, distances)}


def rank_with_faiss(query_embedding, rows, limit):
    try:
        import faiss
        import numpy as np
    except ImportError:
        return None

    matrix = np.asarray([vector for _fact_id, vector in rows], dtype="float32")
    query = np.asarray([query_embedding], dtype="float32")
    if matrix.shape[1] != query.shape[1]:
        return {}
    faiss.normalize_L2(matrix)
    faiss.normalize_L2(query)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    scores, indices = index.search(query, min(limit, len(rows)))
    return {
        rows[index_value][0]: max(0.0, float(score))
        for score, index_value in zip(scores[0], indices[0])
        if index_value >= 0
    }


def rank_with_python(query_embedding, rows):
    return {
        fact_id: cosine_similarity(query_embedding, vector)
        for fact_id, vector in rows
        if len(vector) == len(query_embedding)
    }


def decode_vector(value):
    try:
        payload = json.loads(value or "[]")
        return [float(item) for item in payload]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def cosine_similarity(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
