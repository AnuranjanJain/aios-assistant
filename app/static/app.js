if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

const LOCAL_FORM_TOKEN_COOKIE = "aios_form_token";
const LOCAL_FORM_TOKEN_FIELD = "_local_form_token";
const LOCAL_FORM_TOKEN_HEADER = "X-AiOS-Form-Token";
const UNSAFE_REQUEST_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function attachLocalFormToken(form) {
  if (!form || String(form.method || "get").toUpperCase() === "GET") {
    return;
  }
  const token = readCookie(LOCAL_FORM_TOKEN_COOKIE);
  if (!token) {
    return;
  }
  let input = form.querySelector(`input[name="${LOCAL_FORM_TOKEN_FIELD}"]`);
  if (!input) {
    input = document.createElement("input");
    input.type = "hidden";
    input.name = LOCAL_FORM_TOKEN_FIELD;
    form.appendChild(input);
  }
  input.value = token;
}

const nativeFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => {
  const sourceRequest = input instanceof Request ? input : null;
  const method = String(init.method || sourceRequest?.method || "GET").toUpperCase();
  const url = new URL(sourceRequest?.url || String(input), window.location.href);
  if (!UNSAFE_REQUEST_METHODS.has(method) || url.origin !== window.location.origin) {
    return nativeFetch(input, init);
  }

  const token = readCookie(LOCAL_FORM_TOKEN_COOKIE);
  if (!token) {
    return nativeFetch(input, init);
  }
  const headers = new Headers(init.headers || sourceRequest?.headers || {});
  headers.set(LOCAL_FORM_TOKEN_HEADER, token);
  return nativeFetch(input, { ...init, headers });
};

document.addEventListener("submit", (event) => attachLocalFormToken(event.target), true);

const LIVE_INTERVAL_MS = 8000;
const SIDEBAR_SCROLL_KEY = "aios.sidebar.scrollTop";

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
    achievements: renderAchievements,
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
    const signature = JSON.stringify(items.map((item) => [
      item.id || item.created_at || item.title,
      item.status,
      item.deadline,
      item.summary,
      item.is_done
    ]));
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

function renderAchievements(item) {
  return `
    <article class="achievement-card">
      <span class="achievement-icon">✓</span>
      <small>${escapeHtml(item.program || item.organization || "Opportunity")}</small>
      <strong>${escapeHtml(item.status)}</strong>
      <p>${escapeHtml(item.title)}</p>
    </article>
  `;
}

function renderOpportunities(item) {
  return `
    <article class="list-row ${item.days_left !== null && item.days_left !== undefined && Number(item.days_left) <= 3 ? "opportunity-urgent" : ""}">
      <span class="status-dot"></span>
      <div class="list-copy">
        <strong>${escapeHtml(item.title)}</strong>
        <small class="list-meta">
          <span>${escapeHtml(item.kind)}</span>
          <span>${escapeHtml(item.status)}</span>
          <span>${escapeHtml(item.organization || "Unknown")}</span>
        </small>
        ${item.deadline_message ? `<p class="deadline-copy">${escapeHtml(item.deadline_message)}</p>` : ""}
        ${item.notes ? `<p class="list-summary mail-summary">${escapeHtml(item.notes)}</p>` : ""}
        <small>${escapeHtml(item.source || "Local source")}${item.updated_at ? ` · ${formatTime(item.updated_at)}` : ""}</small>
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
      <div class="list-copy">
        <strong>${escapeHtml(item.title)}</strong>
        <small>${formatTime(item.due_at)}${item.is_read ? " - read" : ""}</small>
        <small class="list-meta"><span>${escapeHtml(item.priority || "normal")}</span><span>${escapeHtml(item.notification_type || "reminder")}</span></small>
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
      <div class="list-copy">
        <strong>${escapeHtml(item.subject)}</strong>
        <small class="list-meta">
          <span>${escapeHtml(item.category)}</span>
          <span>${escapeHtml(item.sender || "Manual input")}</span>
        </small>
        ${item.summary ? `<p class="list-summary mail-summary">${escapeHtml(item.summary)}</p>` : ""}
        ${item.next_action ? `<small class="list-next-action">Next: ${escapeHtml(item.next_action)}</small>` : ""}
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
    achievements: "Selections and round milestones will appear here.",
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
  setupSidebarScrollPersistence();
  enhanceEmptyStates();
  setupSmoothNavigation();
  setupFormBusyStates();
  setupInlineValidation();
  setupMemorySearch();
  setupDesktopExitButton();
  setupGoogleSignInWait();
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

function setupSidebarScrollPersistence() {
  const menu = document.querySelector(".workspace-sidebar .menu");
  if (!menu || menu.dataset.scrollPersistenceReady === "1") {
    return;
  }
  menu.dataset.scrollPersistenceReady = "1";

  let restored = false;
  try {
    const saved = Number(window.sessionStorage.getItem(SIDEBAR_SCROLL_KEY));
    if (Number.isFinite(saved) && saved >= 0) {
      menu.scrollTop = saved;
      restored = true;
    }
  } catch (_error) {
    restored = false;
  }

  if (!restored) {
    menu.querySelector("a.active")?.scrollIntoView({ block: "nearest" });
  }

  const savePosition = () => {
    try {
      window.sessionStorage.setItem(SIDEBAR_SCROLL_KEY, String(menu.scrollTop));
    } catch (_error) {
      // The active-item fallback still keeps navigation usable when storage is unavailable.
    }
  };

  let animationFrame = 0;
  menu.addEventListener("scroll", () => {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = window.requestAnimationFrame(savePosition);
  }, { passive: true });
  menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", savePosition));
  window.addEventListener("pagehide", savePosition);
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
    attachLocalFormToken(form);
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

function setupGoogleSignInWait() {
  const root = document.querySelector("[data-google-sign-in-job]");
  if (!root) {
    return;
  }

  const title = root.querySelector("[data-oauth-title]");
  const message = root.querySelector("[data-oauth-message]");
  const continueButton = root.querySelector("[data-oauth-continue]");
  const cancelButton = root.querySelector("[data-oauth-cancel]");
  const finishLink = root.querySelector("[data-oauth-finish]");
  const progress = root.querySelector("[data-oauth-progress]");
  let terminal = false;
  let pollTimer = 0;

  const terminalTitles = {
    succeeded: "Google account connected",
    failed: "Google sign-in needs attention",
    cancelled: "Sign-in cancelled",
    timed_out: "Sign-in timed out"
  };

  const render = (job) => {
    if (!job) {
      return;
    }
    root.dataset.state = job.status;
    message.textContent = job.message || "Waiting for Google sign-in...";
    continueButton.disabled = !job.can_continue;

    if (!job.terminal) {
      title.textContent = job.status === "starting" ? "Preparing Google sign-in" : "Continue in your browser";
      return;
    }

    terminal = true;
    window.clearInterval(pollTimer);
    title.textContent = terminalTitles[job.status] || "Google sign-in finished";
    continueButton.hidden = true;
    cancelButton.hidden = true;
    finishLink.hidden = false;
    progress.setAttribute("aria-label", title.textContent);
    progress.setAttribute("aria-valuenow", "100");

    if (job.status === "succeeded") {
      window.setTimeout(() => window.location.assign(root.dataset.finishUrl), 900);
    }
  };

  const poll = async () => {
    if (terminal) {
      return;
    }
    try {
      const response = await fetch(root.dataset.statusUrl, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Sign-in status unavailable");
      }
      render(payload.sign_in);
    } catch (_error) {
      message.textContent = "AiOS could not read the sign-in status. You can cancel and try again.";
    }
  };

  continueButton.addEventListener("click", async () => {
    continueButton.disabled = true;
    try {
      const response = await fetch(root.dataset.continueUrl, { method: "POST", cache: "no-store" });
      const payload = await response.json();
      message.textContent = payload.message || "Check your browser to continue.";
      if (!response.ok) {
        continueButton.disabled = false;
      }
    } catch (_error) {
      message.textContent = "AiOS could not open the browser. Check your default browser and try again.";
      continueButton.disabled = false;
    }
  });

  cancelButton.addEventListener("click", async () => {
    cancelButton.disabled = true;
    try {
      const response = await fetch(root.dataset.cancelUrl, { method: "POST", cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Cancel failed");
      }
      render(payload.sign_in);
    } catch (_error) {
      cancelButton.disabled = false;
      message.textContent = "AiOS could not cancel this sign-in. Close the browser window and return to Settings.";
    }
  });

  poll();
  pollTimer = window.setInterval(poll, 1100);
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
