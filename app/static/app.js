if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

const LIVE_INTERVAL_MS = 8000;

async function refreshLiveDashboard() {
  const liveNodes = document.querySelectorAll(
    "[data-live-stat], [data-live-plan-summary], [data-live-list], [data-live-updated]"
  );
  if (!liveNodes.length) {
    return;
  }

  try {
    const response = await fetch("/api/live", {
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      setLiveStatus("Offline");
      return;
    }

    const payload = await response.json();
    updateSummary(payload);
    updateStats(payload);
    updateLists(payload);
    setLiveStatus(`Live sync ${formatTime(payload.updated_at)}`);
  } catch (_error) {
    setLiveStatus("Offline");
  }
}

function updateSummary(payload) {
  document.querySelectorAll("[data-live-plan-summary]").forEach((node) => {
    updateLiveValue(node, payload.plan?.summary || node.textContent);
  });
}

function updateStats(payload) {
  document.querySelectorAll("[data-live-stat]").forEach((node) => {
    const key = node.dataset.liveStat;
    if (Object.prototype.hasOwnProperty.call(payload.stats || {}, key)) {
      updateLiveValue(node, payload.stats[key]);
    }
  });
}

function updateLiveValue(node, value) {
  const next = String(value ?? "");
  if (node.textContent === next) {
    return;
  }
  node.textContent = next;
  node.classList.remove("is-updating");
  void node.offsetWidth;
  node.classList.add("is-updating");
  window.setTimeout(() => node.classList.remove("is-updating"), 300);
}

function updateLists(payload) {
  const listRenderers = {
    opportunities: renderOpportunities,
    reminders: renderReminders,
    activities: renderActivities,
    inbox_items: renderInboxItems,
    connector_runs: renderConnectorRuns
  };

  document.querySelectorAll("[data-live-list]").forEach((node) => {
    const key = node.dataset.liveList;
    const renderer = listRenderers[key];
    if (!renderer) {
      return;
    }

    const items = payload[key] || [];
    const signature = JSON.stringify(items.map((item) => item.id || item.created_at || item.title));
    if (node.dataset.signature === signature) {
      return;
    }

    node.dataset.signature = signature;
    node.innerHTML = items.length ? items.map(renderer).join("") : `<p class="empty">${emptyText(key)}</p>`;
    enhanceEmptyStates(node);
    setupSmoothNavigation();
    setupRevealAnimations(node);
    node.querySelector(".list-row")?.classList.add("is-fresh");
  });
}

function renderOpportunities(item) {
  return `
    <article class="list-row">
      <span class="status-dot"></span>
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <small>${escapeHtml(item.kind)} - ${escapeHtml(item.status)} - ${escapeHtml(item.organization || "Unknown")}</small>
      </div>
    </article>
  `;
}

function renderReminders(item) {
  const actions = !item.is_done && !item.is_read
    ? `<form method="post" action="/reminders/${item.id}/read"><button type="submit" class="ghost-button">Read</button></form>`
    : "";

  return `
    <article class="list-row reminder-row ${item.is_done ? "done" : ""}">
      <div>
        <strong>${escapeHtml(item.title)}</strong>
        <small>${formatTime(item.due_at)}${item.is_read ? " - read" : ""}</small>
      </div>
      ${actions}
    </article>
  `;
}

function renderActivities(item) {
  return `
    <article class="list-row">
      <span class="activity-badge">${Number(item.duration_minutes || 0)}m</span>
      <div>
        <strong>${escapeHtml(item.app_name || item.category || "Activity")}</strong>
        <small>${escapeHtml(item.agent_summary || "Activity logged.")}</small>
      </div>
    </article>
  `;
}

function renderInboxItems(item) {
  return `
    <article class="list-row">
      <span class="confidence">${Math.round(Number(item.confidence || 0) * 100)}%</span>
      <div>
        <strong>${escapeHtml(item.subject)}</strong>
        <small>${escapeHtml(item.category)} - ${escapeHtml(item.sender || "Manual input")}</small>
      </div>
    </article>
  `;
}

function renderConnectorRuns(item) {
  return `
    <article class="list-row">
      <span class="activity-badge">${Number(item.records_imported || 0)}</span>
      <div>
        <strong>${escapeHtml(item.connector_id)} - ${escapeHtml(item.status)}</strong>
        <small>${escapeHtml(item.message || "Connector finished.")}</small>
      </div>
    </article>
  `;
}

function emptyText(key) {
  return {
    opportunities: "Real opportunities will appear after connector or extension capture.",
    reminders: "No reminders waiting.",
    activities: "Desktop and wellbeing activity will appear here.",
    inbox_items: "Classified real inbox items will appear here.",
    connector_runs: "Connector runs will appear here."
  }[key] || "No live data yet.";
}

function setLiveStatus(text) {
  document.querySelectorAll("[data-live-updated]").forEach((node) => {
    node.textContent = text;
  });
}

function formatTime(value) {
  if (!value) {
    return "now";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

window.addEventListener("load", () => {
  refreshLiveDashboard();
  setInterval(refreshLiveDashboard, LIVE_INTERVAL_MS);
  setupDashboardTabs();
  enhanceEmptyStates();
  setupSmoothNavigation();
  setupFormBusyStates();
  setupInlineValidation();
  setupMemorySearch();
  setupDesktopExitButton();
  setupErrorActions();
  setupRevealAnimations();
  loadDesktopStatus();
});

function setupRevealAnimations(root = document) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const selector = [
    ".workspace-hero",
    ".source-hero",
    ".stat-card",
    ".panel",
    ".lead-section",
    ".task-strip",
    ".agent-summary-panel",
    ".list-row",
    ".settings-section"
  ].join(",");
  const nodes = Array.from(root.querySelectorAll(selector))
    .filter((node) => node.dataset.motionReady !== "1");
  if (!nodes.length) {
    return;
  }

  document.documentElement.classList.add("motion-ready");
  nodes.forEach((node, index) => {
    node.dataset.motionReady = "1";
    node.classList.add("motion-item");
    node.style.setProperty("--motion-index", String(index % 8));
  });

  if (reduceMotion || !("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) {
        return;
      }
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -5%", threshold: 0.06 });
  nodes.forEach((node) => observer.observe(node));
}

function setupDashboardTabs() {
  const tabs = Array.from(document.querySelectorAll("[data-dashboard-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-dashboard-tab-panel]"));
  if (!tabs.length || !panels.length) {
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const allowed = new Set(tabs.map((tab) => tab.dataset.dashboardTab));
  const initial = allowed.has(params.get("tab")) ? params.get("tab") : "overview";

  const activate = (name, pushState = false) => {
    tabs.forEach((tab) => {
      const active = tab.dataset.dashboardTab === name;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.dashboardTabPanel !== name;
    });
    if (pushState) {
      const next = new URL(window.location.href);
      next.searchParams.set("tab", name);
      window.history.pushState({ dashboardTab: name }, "", next);
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.dataset.dashboardTab, true));
  });
  window.addEventListener("popstate", () => {
    const nextParams = new URLSearchParams(window.location.search);
    activate(allowed.has(nextParams.get("tab")) ? nextParams.get("tab") : "overview");
  });
  activate(initial);
}

function setupSmoothNavigation() {
  document.querySelectorAll('a[href]').forEach((link) => {
    if (link.dataset.smoothReady === "1") {
      return;
    }
    link.dataset.smoothReady = "1";
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href") || "";
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        link.target ||
        href.startsWith("#") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:")
      ) {
        return;
      }

      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname && url.hash) {
        return;
      }

      event.preventDefault();
      document.body.classList.add("is-leaving");
      window.setTimeout(() => {
        window.location.href = url.href;
      }, 130);
    });
  });
}

function setupFormBusyStates() {
  document.querySelectorAll("form").forEach((form) => {
    if (form.dataset.busyReady === "1") {
      return;
    }
    form.dataset.busyReady = "1";
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"], button:not([type])');
      if (!button || button.disabled) {
        return;
      }
      const original = button.textContent.trim();
      const pendingSurface = form.closest(".list-row, .pipeline-item, .planner-task, .career-row, .browser-job, .automation-run");
      form.classList.add("is-submitting");
      pendingSurface?.classList.add("is-pending");
      form.setAttribute("aria-busy", "true");
      button.setAttribute("aria-busy", "true");
      button.dataset.originalText = original;
      button.textContent = busyText(original);
      showDesktopToast(busyText(original));
    });
  });
}

function setupInlineValidation() {
  document.querySelectorAll("input, select, textarea").forEach((field) => {
    if (field.dataset.validationReady === "1") {
      return;
    }
    field.dataset.validationReady = "1";

    field.addEventListener("invalid", () => showFieldError(field));
    field.addEventListener("input", () => {
      if (field.validity.valid) {
        clearFieldError(field);
      }
    });
    field.addEventListener("change", () => {
      if (field.validity.valid) {
        clearFieldError(field);
      }
    });
  });
}

function showFieldError(field) {
  const owner = field.closest("label") || field.parentElement;
  if (!owner) {
    return;
  }
  let error = owner.querySelector(":scope > .field-error");
  if (!error) {
    error = document.createElement("small");
    error.className = "field-error";
    error.setAttribute("role", "alert");
    owner.appendChild(error);
  }
  error.textContent = field.validationMessage || "Check this field and try again.";
  field.setAttribute("aria-invalid", "true");
}

function clearFieldError(field) {
  const owner = field.closest("label") || field.parentElement;
  owner?.querySelector(":scope > .field-error")?.remove();
  field.removeAttribute("aria-invalid");
}

function busyText(label) {
  const lowered = label.toLowerCase();
  if (lowered.includes("resume")) return "Optimizing resume...";
  if (lowered.includes("analyze")) return "Analyzing...";
  if (lowered.includes("search") || lowered.includes("research")) return "Searching...";
  if (lowered.includes("import")) return "Importing...";
  if (lowered.includes("scan")) return "Scanning...";
  if (lowered.includes("save")) return "Saving...";
  if (lowered.includes("run") || lowered.includes("approve")) return "Running...";
  if (lowered.includes("generate")) return "Generating...";
  return "Working...";
}

function showDesktopToast(message) {
  let toast = document.querySelector("[data-desktop-toast]");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "desktop-toast";
    toast.dataset.desktopToast = "1";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.hidden = false;
}

function enhanceEmptyStates(root = document) {
  const actions = {
    "/planner": ["Create roadmap", "#planner-create", "Try: Learn Operating Systems in four weekly periods."],
    "/planning-events": ["Add event", "#quick-add", "Try: Add a repository task with a deadline and next action."],
    "/automation": ["Build preview", "#automation-command", "Try: Organize a local folder with a safe preview."],
    "/browser-agent": ["Build plan", "#browser-command", "Try: Find remote Python internships."],
    "/career": ["Open career tools", "#career-tools", "Try: Analyze a local repository before targeting a role."],
    "/sources": ["Import data", "#source-import", "Try: Import an EML, MBOX, JSON, or CSV export."],
    "/connectors": ["View connectors", "#connector-list", "Try: Connect Gmail or run a local import connector."],
    "/settings": ["Configure sources", "#connected-accounts", "Try: Connect Gmail and verify local Ollama."],
    "/": ["Connect sources", "/sources", "Try: Connect Gmail or import a local data export."],
    "/mobile": ["Connect sources", "/sources", "Try: Capture an email, job, or deadline."]
  };
  const [primaryLabel, primaryHref, example] = actions[window.location.pathname]
    || ["Connect sources", "/sources", "Try: Add one local source to begin building context."];

  root.querySelectorAll(".empty:not([data-empty-enhanced])").forEach((node) => {
    const explanation = node.textContent.trim() || "This view will update when local data becomes available.";
    node.dataset.emptyEnhanced = "1";
    node.textContent = "";

    const icon = document.createElement("span");
    icon.className = "empty-state-mark";
    icon.setAttribute("aria-hidden", "true");

    const content = document.createElement("span");
    content.className = "empty-state-content";
    const title = document.createElement("strong");
    title.textContent = "Nothing here yet";
    const copy = document.createElement("span");
    copy.textContent = explanation;
    const sample = document.createElement("small");
    sample.textContent = example;
    content.append(title, copy, sample);

    const actionRow = document.createElement("span");
    actionRow.className = "empty-state-actions";
    const primary = document.createElement("a");
    primary.className = "button-primary";
    primary.href = primaryHref;
    primary.textContent = primaryLabel;
    const secondary = document.createElement("a");
    secondary.className = "button-ghost";
    secondary.href = "/";
    secondary.textContent = "Dashboard";
    actionRow.append(primary, secondary);

    node.append(icon, content, actionRow);
  });
}

function setupErrorActions() {
  const retry = document.querySelector("[data-error-retry]");
  const back = document.querySelector("[data-error-back]");
  const copy = document.querySelector("[data-copy-error]");
  const details = document.querySelector("[data-error-details]");

  retry?.addEventListener("click", () => window.location.reload());
  back?.addEventListener("click", () => {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/";
  });
  copy?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(details?.textContent?.trim() || "AiOS error");
      showDesktopToast("Error details copied.");
    } catch (_error) {
      showDesktopToast("Unable to copy error details.");
    }
  });
}

function setupMemorySearch() {
  const form = document.querySelector("[data-memory-search]");
  const answer = document.querySelector("[data-memory-answer]");
  if (!form || !answer) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = new FormData(form).get("query")?.toString().trim();
    if (!query) {
      return;
    }

    answer.hidden = false;
    answer.textContent = "";
    answer.classList.add("skeleton", "memory-answer-skeleton");
    answer.setAttribute("aria-label", "Searching local memory");
    try {
      const response = await fetch("/api/memory/ask", {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query })
      });
      const payload = await response.json();
      answer.classList.remove("skeleton", "memory-answer-skeleton");
      answer.removeAttribute("aria-label");
      answer.textContent = response.ok ? payload.answer : payload.error || "Memory search failed.";
    } catch (_error) {
      answer.classList.remove("skeleton", "memory-answer-skeleton");
      answer.removeAttribute("aria-label");
      answer.textContent = "Local memory is unavailable.";
    }
  });
}

function setupDesktopExitButton() {
  const button = document.querySelector("[data-desktop-exit]");
  if (!button) {
    return;
  }

  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Exiting...";
    try {
      const response = await fetch("/api/desktop/exit", {
        method: "POST",
        cache: "no-store"
      });
      if (!response.ok) {
        button.disabled = false;
        button.textContent = "Exit AiOS";
        showDesktopToast("Exit is only available in the native desktop app.");
      }
    } catch (_error) {
      button.disabled = false;
      button.textContent = "Exit AiOS";
      showDesktopToast("Unable to exit the desktop app.");
    }
  });
}

async function loadDesktopStatus() {
  const node = document.querySelector("[data-desktop-status]");
  if (!node) {
    return;
  }

  try {
    const response = await fetch("/api/desktop/status", { cache: "no-store" });
    const payload = await response.json();
    node.innerHTML = [
      ["Mode", payload.desktop ? "Native desktop" : "Browser development"],
      ["Platform", payload.platform],
      ["Data", payload.data_dir],
      ["Configuration", payload.config_dir],
      ["Imports", payload.imports_dir],
      ["Ollama", payload.ollama_url]
    ].map(([label, value]) => `
      <article class="list-row">
        <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(value)}</small></div>
      </article>
    `).join("");
  } catch (_error) {
    node.innerHTML = '<p class="source-note">Desktop diagnostics unavailable.</p>';
  }
}
