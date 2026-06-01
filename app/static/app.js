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
    node.textContent = payload.plan?.summary || node.textContent;
  });
}

function updateStats(payload) {
  document.querySelectorAll("[data-live-stat]").forEach((node) => {
    const key = node.dataset.liveStat;
    if (Object.prototype.hasOwnProperty.call(payload.stats || {}, key)) {
      node.textContent = payload.stats[key];
    }
  });
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
});
