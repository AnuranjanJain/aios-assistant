const statusNode = document.querySelector("#status");
const apiBaseNode = document.querySelector("#apiBase");
const apiTokenNode = document.querySelector("#apiToken");
const autoCaptureHackathonsNode = document.querySelector("#autoCaptureHackathons");
const categoryNode = document.querySelector("#category");
const durationNode = document.querySelector("#duration");

const endpointByAction = {
  savePage: "/api/ingest-email",
  trackJob: "/api/track-job",
  trackHackathon: "/api/track-hackathon"
};

init();

async function init() {
  const [preferences, localSecrets] = await Promise.all([
    chrome.storage.sync.get(["apiBase", "apiToken", "autoCaptureHackathons"]),
    chrome.storage.local.get(["apiToken"])
  ]);
  const apiToken = localSecrets.apiToken || preferences.apiToken || "";
  if (preferences.apiToken && !localSecrets.apiToken) {
    await chrome.storage.local.set({ apiToken: preferences.apiToken });
    await chrome.storage.sync.remove("apiToken");
  }
  if (preferences.apiBase) {
    apiBaseNode.value = preferences.apiBase;
  }
  apiTokenNode.value = apiToken;
  autoCaptureHackathonsNode.checked = preferences.autoCaptureHackathons !== false;

  apiBaseNode.addEventListener("change", async () => {
    await chrome.storage.sync.set({ apiBase: normalizeApiBase(apiBaseNode.value) });
    apiBaseNode.value = normalizeApiBase(apiBaseNode.value);
  });
  apiTokenNode.addEventListener("change", async () => {
    await chrome.storage.local.set({ apiToken: apiTokenNode.value.trim() });
    await chrome.storage.sync.remove("apiToken");
  });
  autoCaptureHackathonsNode.addEventListener("change", async () => {
    await chrome.storage.sync.set({ autoCaptureHackathons: autoCaptureHackathonsNode.checked });
  });

  for (const [id, endpoint] of Object.entries(endpointByAction)) {
    document.querySelector(`#${id}`).addEventListener("click", () => sendPage(endpoint));
  }

  document.querySelector("#logWellbeing").addEventListener("click", sendWellbeing);
}

async function sendPage(endpoint) {
  setStatus("Reading page...");

  try {
    const page = await getCurrentPageContext();
    const body = {
      title: page.title,
      subject: page.title,
      organization: page.hostname,
      body: buildBody(page),
      source: `browser extension: ${page.url}`
    };

    const result = await postJson(endpoint, body);
    setStatus(`Saved: ${result.classification?.category || "captured"}.`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function sendWellbeing() {
  setStatus("Logging activity...");

  try {
    const page = await getCurrentPageContext();
    const body = {
      source: "what-do-you-do extension",
      app_name: page.hostname,
      category: categoryNode.value,
      duration_minutes: Number(durationNode.value || 0),
      actual_task: page.title
    };

    const result = await postJson("/api/wellbeing/activity", body);
    setStatus(result.agent_summary || "Activity logged.");
  } catch (error) {
    setStatus(error.message);
  }
}

async function getCurrentPageContext() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    throw new Error("No active tab found.");
  }

  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "AIOS_READ_PAGE" });
  } catch (_error) {
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const getMeta = (name) => document
          .querySelector(`meta[name="${name}"], meta[property="${name}"]`)
          ?.getAttribute("content") || "";
        const selection = window.getSelection?.().toString().trim() || "";
        const description = getMeta("description") || getMeta("og:description");
        const title = document.title || getMeta("og:title") || location.hostname;
        const heading = document.querySelector("h1")?.innerText?.trim() || "";
        return {
          title,
          heading,
          selection,
          description,
          url: location.href,
          hostname: location.hostname,
          text: selection || description || heading || title
        };
      }
    });
    if (injected?.result) {
      return injected.result;
    }
    return {
      title: tab.title || "Untitled page",
      heading: "",
      selection: "",
      description: "",
      url: tab.url || "",
      hostname: new URL(tab.url || "http://unknown.local").hostname,
      text: tab.title || ""
    };
  }
}

function buildBody(page) {
  return [
    page.heading ? `Heading: ${page.heading}` : "",
    page.selection ? `Selected text: ${page.selection}` : "",
    page.description ? `Description: ${page.description}` : "",
    `URL: ${page.url}`
  ].filter(Boolean).join("\n\n");
}

async function postJson(endpoint, body) {
  const response = await fetch(`${normalizeApiBase(apiBaseNode.value)}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(apiTokenNode.value.trim() ? { "X-AiOS-Token": apiTokenNode.value.trim() } : {})
    },
    body: JSON.stringify(body)
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }

  return payload;
}

function normalizeApiBase(value) {
  return (value || "http://127.0.0.1:5000").replace(/\/+$/, "");
}

function setStatus(message) {
  statusNode.textContent = message;
}
