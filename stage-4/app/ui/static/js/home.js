// Dossier list with search, and the research form. Research navigates only after success.
import { call, errorMessage, NetworkError } from "/static/js/api.js";
import { clearSession } from "/static/js/session.js";
import { createLatestReads } from "/static/js/latest.js";
import { createPending } from "/static/js/pending.js";
import { FIELD_LABELS, STATE_LABELS, providerLabel } from "/static/js/format.js";

const list = document.getElementById("dossier-list");
const listStatus = document.getElementById("list-status");
const emptyBox = document.querySelector('[data-testid="empty-dossiers"]');
const search = document.querySelector('[data-testid="dossier-search"]');
const reads = createLatestReads();
const pending = createPending();
const researchForm = document.getElementById("research-form");
const domainInput = document.querySelector('[data-testid="research-domain"]');
const researchError = document.querySelector('[data-testid="research-error"]');
const researchUncertain = document.querySelector('[data-testid="research-uncertain"]');
const researchSubmit = document.querySelector('[data-testid="research-submit"]');

function renderItem(item) {
  const row = document.createElement("li");
  row.dataset.testid = `dossier-item-${item.domain}`;
  row.dataset.state = item.state;
  const link = document.createElement("a");
  link.href = `/dossiers/${encodeURIComponent(item.domain)}`;
  link.className = "domain";
  link.textContent = item.domain;
  const name = document.createElement("span");
  name.className = "name";
  name.textContent = item.legal_name || "";
  const state = document.createElement("span");
  state.className = `badge state-${item.state}`;
  state.textContent = STATE_LABELS[item.state] || item.state;
  row.append(link, name, state);
  return row;
}

async function loadList() {
  const seq = reads.start();
  const query = search.value.trim();
  const path = `/dossiers?limit=50${query ? `&q=${encodeURIComponent(query)}` : ""}`;
  let result;
  try {
    result = await call(path);
  } catch (error) {
    if (!reads.accept(seq)) return;
    listStatus.textContent = error instanceof NetworkError
      ? "Could not load dossiers. Reload to try again."
      : "Could not load dossiers.";
    return;
  }
  if (!reads.accept(seq)) return; // a later read has already applied
  if (result.status === 401) {
    clearSession();
    list.replaceChildren();
    emptyBox.hidden = true;
    listStatus.innerHTML = '<a href="/login">Log in</a> to see dossiers.';
    return;
  }
  if (result.status !== 200) {
    listStatus.textContent = errorMessage(result, "Could not load dossiers.");
    return;
  }
  const items = result.data.dossiers;
  list.replaceChildren(...items.map(renderItem));
  emptyBox.hidden = items.length > 0;
  listStatus.textContent = result.data.has_more
    ? "Showing the first 50 matches. Refine the search to see more."
    : "";
}

function showResearchError(message) {
  researchUncertain.hidden = true;
  researchError.textContent = message;
  researchError.hidden = false;
}

researchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = { domain: domainInput.value };
  const request = pending.forBody(body);
  researchSubmit.disabled = true;
  researchError.hidden = true;
  try {
    const result = await call("/dossiers", { method: "POST", body, key: request.key });
    pending.clear();
    if (result.status === 202 || result.status === 200) {
      // The write succeeded; only now does the browser navigate to the dossier.
      window.location.assign(`/dossiers/${encodeURIComponent(result.data.domain)}`);
      return;
    }
    researchUncertain.hidden = true;
    showResearchError(errorMessage(result, "The research request was refused."));
  } catch (error) {
    if (error instanceof NetworkError) {
      researchUncertain.hidden = false;
      researchSubmit.textContent = "Retry research";
      return;
    }
    pending.clear();
    showResearchError("The research request failed. Try again.");
  } finally {
    researchSubmit.disabled = false;
  }
});

let searchTimer = null;
search.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadList, 200);
});

loadList();
