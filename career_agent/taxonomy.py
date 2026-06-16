import re


SKILL_ALIASES = {
    "python": {"python", "fastapi", "flask", "django", "pandas", "numpy", "pyautogui", "pytest"},
    "javascript": {"javascript", "typescript", "node", "react", "vite", "next", "express"},
    "data": {"sqlite", "postgresql", "mysql", "chroma", "faiss", "etl", "analytics"},
    "ai": {"ollama", "llm", "rag", "agent", "automation", "ocr", "playwright"},
    "devops": {"docker", "github actions", "ci", "linux", "arch", "packaging"},
    "product": {"dashboard", "pwa", "ux", "accessibility", "documentation"},
}

TECH_KEYWORDS = {
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "React": ("react", "jsx", "tsx"),
    "Vite": ("vite",),
    "SQLite": ("sqlite",),
    "ChromaDB": ("chromadb", "chroma"),
    "FAISS": ("faiss",),
    "Ollama": ("ollama",),
    "Playwright": ("playwright",),
    "PyAutoGUI": ("pyautogui",),
    "LibreOffice": ("libreoffice", "soffice"),
    "Tailwind": ("tailwind",),
    "Docker": ("docker", "dockerfile"),
    "GitHub Actions": ("github/workflows", "actions/checkout"),
}

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".md": "Markdown",
    ".dart": "Dart",
    ".java": "Java",
    ".kt": "Kotlin",
    ".cpp": "C++",
    ".c": "C",
    ".rs": "Rust",
    ".go": "Go",
}

ACTION_VERBS = (
    "Built",
    "Implemented",
    "Automated",
    "Designed",
    "Optimized",
    "Integrated",
    "Secured",
    "Analyzed",
)


def normalize_terms(text):
    return {term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{1,}", text or "")}


def extract_technologies(text):
    lowered = (text or "").lower()
    return sorted(
        technology
        for technology, needles in TECH_KEYWORDS.items()
        if any(needle in lowered for needle in needles)
    )


def group_skills(technologies, text=""):
    corpus = " ".join([text or "", " ".join(technologies)]).lower()
    groups = []
    for group, needles in SKILL_ALIASES.items():
        if any(needle in corpus for needle in needles):
            groups.append(group)
    return sorted(groups)
