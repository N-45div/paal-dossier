// One dossier: reads the JSON API, renders fields with citations, refreshes, and follows a build.
import { call, errorMessage, NetworkError } from "/static/js/api.js";
import { clearSession } from "/static/js/session.js";
import { createLatestReads } from "/static/js/latest.js";
import { createPending } from "/static/js/pending.js";
import {
  FIELD_LABELS, STATUS_LABELS, formatValue, formatWhen, providerLabel,
} from "/static/js/format.js";

const POLL_MS = 1500; // the spec asks for a read at least every 2 seconds while building

const root = document.getElementById("dossier-root");
const domain = root.dataset.domain;
const endpoint = `/dossiers/${encodeURIComponent(domain)}`;
const stateBadge = document.querySelector('[data-testid="dossier-state"]');
const spent = document.querySelector('[data-testid="dossier-spent"]');
const researchedAt = document.querySelector('[data-testid="dossier-researched-at"]');
const fieldsBox = document.getElementById("dossier-fields");
const statusLine = document.getElementById("dossier-status");
const authBox = document.getElementById("dossier-auth");
const notFound = root.querySelector(".not-found");
const refreshButton = document.querySelector('[data-testid="dossier-refresh"]');
const reloadButton = document.querySelector('[data-testid="dossier-reload"]');
const refreshError = document.querySelector('[data-testid="refresh-error"]');
const refreshUncertain = document.querySelector('[data-testid="refresh-uncertain"]');

const reads = createLatestReads();
const pending = createPending();
let pollTimer = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderSummary(dossier) {
  stateBadge.textContent = dossier.state; // exactly building, ready or failed
  stateBadge.className = `badge state-${dossier.state}`;
  stateBadge.dataset.state = dossier.state;
  spent.textContent = `${Number(dossier.spent_units).toLocaleString("en-US")} units spent`;
  spent.dataset.units = String(dossier.spent_units);
  if (dossier.researched_at) {
    researchedAt.textContent = `Researched ${formatWhen(dossier.researched_at)}`;
    researchedAt.hidden = false;
  } else {
    researchedAt.textContent = "";
    researchedAt.hidden = true;
  }
  if (dossier.state === "building") {
    statusLine.textContent = "Research is running. This page updates when it finishes.";
  } else if (dossier.state === "failed") {
    statusLine.textContent = "The latest build failed. You can refresh to try again.";
  } else {
    statusLine.textContent = "";
  }
}

function renderCitation(field, citation, index) {
  const item = el("li", "citation");
  item.dataset.testid = `citation-${field}-${index + 1}`;
  item.dataset.provider = citation.provider;
  const quote = el("blockquote");
  quote.append(el("p", "", citation.excerpt));
  const source = el("p", "source");
  source.append(
    el("span", "provider", providerLabel(citation.provider)), " · ",
  );
  const link = el("a", "", citation.url);
  link.href = citation.url;
  link.rel = "noopener noreferrer";
  source.append(link);
  item.append(quote, source);
  return item;
}

function renderField(name, field) {
  const block = el("article", "field");
  block.dataset.testid = `field-${name}`;
  block.dataset.status = field.status;

  const title = el("div", "field-title");
  title.append(el("h2", "", FIELD_LABELS[name] || name));
  title.append(el("span", `badge ${field.status}`, STATUS_LABELS[field.status] || field.status));
  block.append(title);

  if (field.value !== null) {
    const value = el("p", "field-value", formatValue(name, field.value));
    value.dataset.testid = `field-value-${name}`;
    value.dataset.value = String(field.value);
    block.append(value);
  } else {
    block.append(el("p", "field-empty", "No value found yet."));
  }

  if (field.status === "contested") {
    const marker = el("p", "contested-note", "Sources disagree. The value shown is the selected one.");
    marker.dataset.testid = `field-contested-${name}`;
    block.append(marker);
  }

  const citations = el("ul", "citations");
  citations.dataset.testid = `field-citations-${name}`;
  field.citations.forEach((citation, index) => {
    citations.append(renderCitation(name, citation, index));
  });
  block.append(citations);
  return block;
}

function renderFields(dossier) {
  fieldsBox.replaceChildren(
    ...Object.entries(dossier.fields).map(([name, field]) => renderField(name, field)),
  );
}

function showNotFound() {
  stopPolling();
  fieldsBox.replaceChildren();
  notFound.hidden = false;
  statusLine.textContent = "";
  stateBadge.textContent = "Not found";
  stateBadge.className = "badge";
  spent.textContent = "";
  researchedAt.hidden = true;
}

function stopPolling() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
}

function schedulePoll() {
  stopPolling();
  pollTimer = window.setTimeout(read, POLL_MS);
}

// Read the dossier again. Only the newest read applies, and a read while building repeats.
async function read() {
  stopPolling();
  const seq = reads.start();
  let result;
  try {
    result = await call(endpoint);
  } catch (error) {
    if (!reads.accept(seq)) return;
    statusLine.textContent = error instanceof NetworkError
      ? "Could not reach the service. Use Reload to try again."
      : "Could not load this dossier.";
    return;
  }
  if (!reads.accept(seq)) return;
  if (result.status === 401) {
    clearSession();
    authBox.hidden = false;
    statusLine.textContent = "";
    return;
  }
  if (result.status === 404) {
    showNotFound();
    return;
  }
  if (result.status !== 200) {
    statusLine.textContent = errorMessage(result, "Could not load this dossier.");
    return;
  }
  authBox.hidden = true;
  notFound.hidden = true;
  renderSummary(result.data);
  renderFields(result.data);
  if (result.data.state === "building") schedulePoll();
}

function showRefreshError(message) {
  refreshUncertain.hidden = true;
  refreshError.textContent = message;
  refreshError.hidden = false;
}

refreshButton.addEventListener("click", async () => {
  const request = pending.forBody(null);
  refreshButton.disabled = true;
  refreshError.hidden = true;
  try {
    const result = await call(`${endpoint}/refresh`, { method: "POST", key: request.key });
    pending.clear();
    refreshUncertain.hidden = true;
    if (result.status === 202 || result.status === 200) {
      await read(); // the write succeeded: show the building state and follow the build
      return;
    }
    showRefreshError(errorMessage(result, "The refresh was refused."));
  } catch (error) {
    if (error instanceof NetworkError) {
      refreshError.hidden = true;
      refreshUncertain.hidden = false;
      refreshButton.textContent = "Retry refresh";
      return;
    }
    pending.clear();
    showRefreshError("The refresh failed. Try again.");
  } finally {
    refreshButton.disabled = false;
  }
});

reloadButton.addEventListener("click", () => {
  read();
});

read();
