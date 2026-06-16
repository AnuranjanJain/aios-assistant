from dataclasses import asdict, dataclass, field
from typing import Protocol
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from browser_agent.scoring import extract_skills


@dataclass
class BrowserResult:
    ok: bool
    summary: str
    data: dict = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


class BrowserBackend(Protocol):
    def open(self, url): ...
    def navigate(self, url): ...
    def extract_page(self, **arguments): ...
    def extract_jobs(self, **arguments): ...
    def fill_form(self, **arguments): ...
    def click_submit(self, **arguments): ...
    def close(self): ...


class PlaywrightBrowserBackend:
    JOB_SELECTORS = (
        "article",
        "[data-job-id]",
        ".job_seen_beacon",
        ".job-card-container",
        ".jobTuple",
        ".internship_meta",
    )

    def __init__(self, config):
        self.config = config
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure(self):
        if self._page:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Install requirements-browser.txt.") from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        self._context = self._browser.new_context(
            accept_downloads=True,
            user_agent="AiOS Browser Agent/0.1 (local user-controlled automation)",
        )
        self._page = self._context.new_page()

    def open(self, url):
        self._ensure()
        self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return BrowserResult(True, f"Opened {urlsplit(url).hostname}.", {"url": self._page.url})

    def navigate(self, url):
        return self.open(url)

    def extract_page(self, **_arguments):
        self._ensure()
        title = self._page.title()
        text = self._page.locator("body").inner_text(timeout=10_000)[:20_000]
        return BrowserResult(
            True,
            f"Extracted {title}.",
            {"title": title, "url": self._page.url, "text": text, "skills": extract_skills(text)},
        )

    def extract_jobs(self, source="", max_results=25, **_arguments):
        self._ensure()
        jobs = []
        for selector in self.JOB_SELECTORS:
            cards = self._page.locator(selector)
            count = min(cards.count(), max_results)
            if not count:
                continue
            for index in range(count):
                card = cards.nth(index)
                text = card.inner_text(timeout=5_000).strip()
                if len(text) < 20:
                    continue
                link = card.locator("a[href]").first
                href = link.get_attribute("href") if link.count() else self._page.url
                title = text.splitlines()[0][:180]
                company = text.splitlines()[1][:180] if len(text.splitlines()) > 1 else "Unknown"
                jobs.append(
                    {
                        "source": source or urlsplit(self._page.url).hostname,
                        "source_url": urljoin(self._page.url, href or self._page.url),
                        "title": title,
                        "company": company,
                        "description": text[:5000],
                        "skills": extract_skills(text),
                    }
                )
            if jobs:
                break
        return BrowserResult(True, f"Extracted {len(jobs)} job result(s).", {"jobs": jobs, "url": self._page.url})

    def click(self, selector="", role="", name=""):
        self._ensure()
        locator = self._page.get_by_role(role, name=name, exact=True) if role and name else self._page.locator(selector)
        if locator.count() != 1:
            raise RuntimeError("Click target is missing or ambiguous.")
        text = (locator.inner_text(timeout=5_000) or "").lower()
        if any(term in text for term in ("apply", "buy", "pay", "send", "submit", "confirm")):
            raise PermissionError("This click may create an external side effect and needs action-time approval.")
        locator.click()
        return BrowserResult(True, f"Clicked {name or selector}.", {"url": self._page.url})

    def fill_form(self, fields=None, **_arguments):
        self._ensure()
        filled = []
        for label, value in (fields or {}).items():
            locator = self._page.get_by_label(label, exact=True)
            if locator.count() != 1:
                raise RuntimeError(f"Form field is missing or ambiguous: {label}")
            locator.fill(str(value))
            filled.append(label)
        return BrowserResult(True, f"Prepared {len(filled)} application field(s); nothing submitted.", {"fields": filled})

    def download(self, selector, suggested_name=""):
        self._ensure()
        locator = self._page.locator(selector)
        if locator.count() != 1:
            raise RuntimeError("Download target is missing or ambiguous.")
        with self._page.expect_download(timeout=30_000) as download_info:
            locator.click()
        download = download_info.value
        filename = suggested_name or download.suggested_filename
        destination = Path(self.config.data_dir) / "downloads" / Path(filename).name
        download.save_as(destination)
        return BrowserResult(True, f"Downloaded {destination.name}.", {"path": str(destination)})

    def manage_tabs(self, action="list", index=None):
        self._ensure()
        pages = self._context.pages
        if action == "list":
            return BrowserResult(True, f"{len(pages)} tab(s) open.", {"tabs": [{"title": page.title(), "url": page.url} for page in pages]})
        if action == "new":
            self._page = self._context.new_page()
            return BrowserResult(True, "Opened a new tab.")
        if action == "switch" and index is not None and 0 <= int(index) < len(pages):
            self._page = pages[int(index)]
            self._page.bring_to_front()
            return BrowserResult(True, f"Switched to tab {index}.", {"url": self._page.url})
        if action == "close" and len(pages) > 1:
            self._page.close()
            self._page = self._context.pages[-1]
            return BrowserResult(True, "Closed the active tab.")
        raise ValueError("Unsupported or unsafe tab operation.")

    def click_submit(self, selector=""):
        raise PermissionError("Submission requires a separate action-time approval and is disabled in the MVP.")

    def close(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = self._context = self._browser = self._playwright = None


class BrowserMCPBridge:
    """Structured contract for a trusted Browser MCP host."""

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def __getattr__(self, operation):
        return lambda **arguments: BrowserResult(
            True,
            f"Browser MCP completed {operation}.",
            self.dispatcher({"operation": operation, "arguments": arguments}),
        )
