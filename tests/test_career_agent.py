import subprocess

from career_agent.config import CareerConfig
from career_agent.engine import CareerCopilotEngine


def build_sample_repo(tmp_path):
    repo = tmp_path / "sample-aios"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Sample AiOS\n\nFastAPI, React, SQLite, Playwright and Ollama local agent dashboard.\n" * 20,
        encoding="utf-8",
    )
    (repo / "requirements.txt").write_text("fastapi\nflask\nplaywright\n", encoding="utf-8")
    (repo / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"}}', encoding="utf-8")
    (repo / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef home(): return {'ok': True}\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    try:
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "AiOS Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass
    return repo


def make_engine(tmp_path):
    return CareerCopilotEngine(CareerConfig(data_dir=tmp_path / "career-data", github_token=""))


def test_repository_analysis_builds_portfolio_and_graph(tmp_path):
    engine = make_engine(tmp_path)
    repo = build_sample_repo(tmp_path)

    result = engine.analyze_repository(str(repo), "AiOS")

    assert result["repository"]["languages"]["Python"] > 0
    assert "FastAPI" in result["repository"]["frameworks"]
    assert result["project"]["name"] == "AiOS"
    dashboard = engine.dashboard()
    assert dashboard["counts"]["repositories"] == 1
    assert any(node["type"] == "Technology" for node in dashboard["graph"]["nodes"])


def test_job_matching_resume_roadmap_and_application_storage(tmp_path):
    engine = make_engine(tmp_path)
    repo = build_sample_repo(tmp_path)
    engine.analyze_repository(str(repo), "AiOS")

    jd = "AI Engineer Intern using Python, FastAPI, React, SQLite, Playwright and local LLM agents."
    match = engine.match_job(jd, "AI Engineer Intern", "Local AI Co")
    resume = engine.optimize_resume("Python developer building local AI systems.", jd)
    application_id = engine.save_application(
        {"company": "Local AI Co", "role": "AI Engineer Intern", "status": "applied"}
    )
    roadmap = engine.roadmap_for("AI Engineer")

    assert match["overall_score"] >= 50
    assert "FastAPI" in resume["optimized_text"]
    assert application_id
    assert "30_days" in roadmap["plans"]
    assert engine.search("FastAPI local agent")
