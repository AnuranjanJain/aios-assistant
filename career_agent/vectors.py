from career_agent.taxonomy import normalize_terms


class LocalVectorIndex:
    def __init__(self, store):
        self.store = store

    def index(self, source_type, source_id, text):
        self.store.save_vector_document(source_type, source_id, text, normalize_terms(text))

    def search(self, query, limit=10):
        return self.store.search_documents(normalize_terms(query), limit=limit)
