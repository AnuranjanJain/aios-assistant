const HACKATHON_HOSTS = ["unstop.com", "hack2skill.com", "hackerearth.com", "devfolio.co", "devpost.com"];

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab.url || !isHackathonPage(tab.url)) {
    return;
  }

  const [settings, localSecrets] = await Promise.all([
    chrome.storage.sync.get(["apiBase", "autoCaptureHackathons"]),
    chrome.storage.local.get(["apiToken"])
  ]);
  if (settings.autoCaptureHackathons === false) {
    return;
  }

  const captureKey = `captured:${normalizePageUrl(tab.url)}`;
  const captured = await chrome.storage.local.get([captureKey]);
  if (captured[captureKey]) {
    return;
  }

  try {
    const page = await chrome.tabs.sendMessage(tabId, { type: "AIOS_READ_PAGE" });
    const platform = detectPlatform(page.hostname || tab.url);
    const response = await fetch(`${normalizeApiBase(settings.apiBase)}/api/hackathons/capture`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(localSecrets.apiToken ? { "X-AiOS-Token": localSecrets.apiToken } : {})
      },
      body: JSON.stringify({
        title: page.heading || page.title,
        organization: platform,
        platform,
        url: page.url,
        source: `browser extension:${page.url}`,
        body: [page.description, page.text].filter(Boolean).join("\n"),
        external_id: `page:${normalizePageUrl(page.url)}`
      })
    });

    if (response.ok) {
      await chrome.storage.local.set({ [captureKey]: new Date().toISOString() });
    }
  } catch (_error) {
    // The next page visit retries automatically.
  }
});

function isHackathonPage(value) {
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return HACKATHON_HOSTS.some((host) => hostname === host || hostname.endsWith(`.${host}`));
  } catch (_error) {
    return false;
  }
}

function detectPlatform(value) {
  const lowered = String(value || "").toLowerCase();
  if (lowered.includes("hack2skill")) return "hack2skill";
  if (lowered.includes("hackerearth")) return "hackerearth";
  if (lowered.includes("devfolio")) return "devfolio";
  if (lowered.includes("devpost")) return "devpost";
  return "unstop";
}

function normalizePageUrl(value) {
  try {
    const url = new URL(value);
    url.hash = "";
    ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].forEach((key) => {
      url.searchParams.delete(key);
    });
    return url.toString();
  } catch (_error) {
    return value;
  }
}

function normalizeApiBase(value) {
  return (value || "http://127.0.0.1:5000").replace(/\/+$/, "");
}
