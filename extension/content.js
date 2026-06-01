function getMetaContent(name) {
  const node = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
  return node ? node.getAttribute("content") || "" : "";
}

function readPageContext() {
  const selection = window.getSelection ? window.getSelection().toString().trim() : "";
  const description = getMetaContent("description") || getMetaContent("og:description");
  const title = document.title || getMetaContent("og:title") || location.hostname;
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

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "AIOS_READ_PAGE") {
    return false;
  }

  sendResponse(readPageContext());
  return true;
});
