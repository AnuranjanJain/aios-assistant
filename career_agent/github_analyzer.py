import json
import subprocess
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from career_agent.taxonomy import LANGUAGE_EXTENSIONS, extract_technologies, group_skills


IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
}
SENSITIVE_NAMES = {".env", "credentials", "token", "secret", "private", "key"}
PACKAGE_FILES = {"package.json", "pyproject.toml", "requirements.txt", "pubspec.yaml", "pom.xml"}


class GitHubAnalyzer:
    def __init__(self, config):
        self.config = config

    def analyze(self, source):
        source = (source or "").strip()
        if not source:
            raise ValueError("Repository path or GitHub URL is required.")
        if source.startswith(("http://", "https://")):
            return self._analyze_remote(source)
        return self._analyze_local(Path(source).expanduser())

    def _analyze_local(self, repo_path):
        repo_path = repo_path.resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        files = list(self._iter_safe_files(repo_path))
        languages, loc = self._language_breakdown(files)
        package_text = self._package_text(files)
        readme_text = self._readme_text(repo_path)
        corpus = "\n".join([package_text, readme_text, "\n".join(str(path.relative_to(repo_path)) for path in files)])
        frameworks = extract_technologies(corpus)
        technologies = sorted(set(frameworks + group_skills(frameworks, corpus)))
        architecture = self._architecture(repo_path, files)
        complexity = self._complexity(files, loc)
        documentation = self._documentation(repo_path, readme_text)
        commit_activity = self._commit_activity(repo_path)
        score = self._score(languages, frameworks, architecture, complexity, documentation, commit_activity)
        name = repo_path.name
        return {
            "name": name,
            "source": "local",
            "source_url": "",
            "local_path": str(repo_path),
            "languages": languages,
            "frameworks": frameworks,
            "technologies": technologies,
            "architecture": architecture,
            "complexity": complexity,
            "documentation": documentation,
            "commit_activity": commit_activity,
            "score": score,
        }

    def _analyze_remote(self, url):
        owner, repo = self._parse_github_url(url)
        if not owner or not repo:
            raise ValueError("Only GitHub repository URLs are supported for remote analysis.")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "AiOS-Career-Copilot"}
        if self.config.github_token:
            headers["Authorization"] = f"Bearer {self.config.github_token}"

        repo_data = self._github_json(f"https://api.github.com/repos/{owner}/{repo}", headers)
        languages = self._github_json(f"https://api.github.com/repos/{owner}/{repo}/languages", headers)
        readme_text = self._github_readme(owner, repo, headers)
        contents = self._github_contents(owner, repo, headers)
        corpus = "\n".join([readme_text, " ".join(contents)])
        frameworks = extract_technologies(corpus)
        technologies = sorted(set(frameworks + group_skills(frameworks, corpus)))
        architecture = {
            "style": "Remote repository scan",
            "signals": contents[:20],
            "entrypoints": [item for item in contents if item.lower() in {"app.py", "main.py", "package.json", "pyproject.toml"}],
        }
        complexity = {
            "files_scanned": len(contents),
            "lines_of_code": 0,
            "level": "medium" if repo_data.get("size", 0) > 500 else "small",
        }
        documentation = self._documentation(Path(repo), readme_text, remote_files=contents)
        commit_activity = {
            "recent_commits": min(int(repo_data.get("open_issues_count", 0)), 99),
            "default_branch": repo_data.get("default_branch", "main"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
        }
        score = self._score(languages, frameworks, architecture, complexity, documentation, commit_activity)
        return {
            "name": repo_data.get("name", repo),
            "source": "github_api",
            "source_url": url,
            "local_path": "",
            "languages": languages,
            "frameworks": frameworks,
            "technologies": technologies,
            "architecture": architecture,
            "complexity": complexity,
            "documentation": documentation,
            "commit_activity": commit_activity,
            "score": score,
        }

    def _iter_safe_files(self, repo_path):
        count = 0
        for path in repo_path.rglob("*"):
            if count >= self.config.max_files_per_repo:
                break
            if not path.is_file():
                continue
            parts = {part.lower() for part in path.relative_to(repo_path).parts}
            if parts & IGNORE_DIRS:
                continue
            if any(marker in part for part in parts for marker in SENSITIVE_NAMES):
                continue
            if path.stat().st_size > self.config.max_file_bytes:
                continue
            count += 1
            yield path

    def _language_breakdown(self, files):
        bytes_by_language = Counter()
        total_loc = 0
        for path in files:
            language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
            if not language:
                continue
            size = path.stat().st_size
            bytes_by_language[language] += size
            try:
                total_loc += len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError:
                pass
        total = sum(bytes_by_language.values()) or 1
        return (
            {language: round(size * 100 / total, 1) for language, size in bytes_by_language.most_common()},
            total_loc,
        )

    def _package_text(self, files):
        chunks = []
        for path in files:
            if path.name in PACKAGE_FILES:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore")[:8000])
        return "\n".join(chunks)

    def _readme_text(self, repo_path):
        for name in ("README.md", "readme.md", "README.txt"):
            path = repo_path / name
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore")[:12000]
        return ""

    def _architecture(self, repo_path, files):
        rels = [str(path.relative_to(repo_path)).replace("\\", "/") for path in files]
        signals = []
        if any(item.startswith("tests/") or item.startswith("test_") for item in rels):
            signals.append("test suite")
        if any(item.startswith("docs/") for item in rels):
            signals.append("documentation folder")
        if any(item.startswith("app/") for item in rels):
            signals.append("application package")
        if any(item.startswith("api/") or item.endswith("api.py") for item in rels):
            signals.append("API layer")
        if any(item.endswith("Dockerfile") or item == "docker-compose.yml" for item in rels):
            signals.append("containerization")
        if any(item.startswith(".github/workflows/") for item in rels):
            signals.append("CI pipeline")
        entrypoints = [item for item in rels if Path(item).name in {"app.py", "main.py", "run.py", "server.py", "package.json"}]
        style = "Modular service" if len(signals) >= 3 else "Single app" if entrypoints else "Project folder"
        return {"style": style, "signals": signals, "entrypoints": entrypoints[:8]}

    def _complexity(self, files, loc):
        file_count = len(files)
        level = "large" if file_count > 600 or loc > 35000 else "medium" if file_count > 120 or loc > 7000 else "small"
        return {"files_scanned": file_count, "lines_of_code": loc, "level": level}

    def _documentation(self, repo_path, readme_text, remote_files=None):
        if remote_files is not None:
            files = set(remote_files)
        elif repo_path.exists():
            files = {path.name for path in repo_path.iterdir()}
        else:
            files = set()
        has_readme = bool(readme_text)
        has_license = any(name.lower().startswith("license") for name in files)
        has_tests = any("test" in name.lower() for name in files)
        readme_words = len(readme_text.split())
        score = min(100, (35 if has_readme else 0) + (20 if readme_words > 250 else 8 if has_readme else 0) + (15 if has_license else 0) + (20 if has_tests else 0) + 10)
        return {
            "has_readme": has_readme,
            "has_license": has_license,
            "has_tests": has_tests,
            "readme_words": readme_words,
            "score": score,
        }

    def _commit_activity(self, repo_path):
        if not (repo_path / ".git").exists():
            return {"recent_commits": 0, "last_commit": "", "active_days": 0}
        try:
            output = subprocess.check_output(
                ["git", "-C", str(repo_path), "log", "--since=90 days ago", "--pretty=%ad", "--date=short"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except (subprocess.SubprocessError, OSError):
            return {"recent_commits": 0, "last_commit": "", "active_days": 0}
        dates = [line.strip() for line in output.splitlines() if line.strip()]
        return {"recent_commits": len(dates), "last_commit": dates[0] if dates else "", "active_days": len(set(dates))}

    def _score(self, languages, frameworks, architecture, complexity, documentation, commit_activity):
        score = 25
        score += min(20, len(languages) * 5)
        score += min(20, len(frameworks) * 4)
        score += min(15, len(architecture.get("signals", [])) * 4)
        score += 10 if complexity.get("level") in {"medium", "large"} else 4
        score += round(documentation.get("score", 0) * 0.15)
        score += min(10, commit_activity.get("recent_commits", 0))
        return max(0, min(100, int(score)))

    def _parse_github_url(self, url):
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc:
            return "", ""
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 2:
            return "", ""
        return parts[0], parts[1].removesuffix(".git")

    def _github_json(self, url, headers):
        try:
            with urlopen(Request(url, headers=headers), timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"GitHub analysis failed: {exc}") from exc

    def _github_readme(self, owner, repo, headers):
        try:
            with urlopen(Request(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md", headers=headers), timeout=12) as response:
                return response.read().decode("utf-8", errors="ignore")[:12000]
        except (HTTPError, URLError, TimeoutError):
            return ""

    def _github_contents(self, owner, repo, headers):
        try:
            data = self._github_json(f"https://api.github.com/repos/{owner}/{repo}/contents", headers)
        except ValueError:
            return []
        return [item.get("name", "") for item in data if item.get("name")]
