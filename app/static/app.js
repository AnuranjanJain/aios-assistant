if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

const LIVE_INTERVAL_MS = 15000;

async function refreshLiveDashboard() {
  const liveNodes = document.querySelectorAll("[data-live-stat], [data-live-plan-summary]");
  if (!liveNodes.length) {
    return;
  }

  try {
    const response = await fetch("/api/live", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    document.querySelectorAll("[data-live-plan-summary]").forEach((node) => {
      node.textContent = payload.plan?.summary || node.textContent;
    });

    document.querySelectorAll("[data-live-stat]").forEach((node) => {
      const key = node.dataset.liveStat;
      if (Object.prototype.hasOwnProperty.call(payload.stats || {}, key)) {
        node.textContent = payload.stats[key];
      }
    });
  } catch (_error) {
    // The app is local-first; temporary offline states are expected.
  }
}

window.addEventListener("load", () => {
  refreshLiveDashboard();
  setInterval(refreshLiveDashboard, LIVE_INTERVAL_MS);
});
