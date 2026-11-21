// Contested fields across all dossiers. The list API gives summaries only, so each dossier is read
// once to find its contested fields. Latest read wins.
import { call, errorMessage, NetworkError } from "/static/js/api.js";
import { clearSession } from "/static/js/session.js";
import { createLatestReads } from "/static/js/latest.js";
import { FIELD_LABELS, formatValue } from "/static/js/format.js";

const statusLine = document.getElementById("contested-status");
const list = document.getElementById("contested-list");
const emptyBox = document.querySelector('[data-testid="empty-contested"]');
const authBox = document.getElementById("contested-auth");
const reads = createLatestReads();
const PAGE_SIZE = 200;

// Every dossier summary, following has_more so no dossier is missed.
async function allDossiers() {
  const summaries = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const result = await call(`/dossiers?limit=${PAGE_SIZE}&offset=${offset}`);
    if (result.status !== 200) return { result };
    summaries.push(...result.data.dossiers);
    if (!result.data.has_more) return { summaries };
  }
}

function contestedItems(dossier) {
  const items = [];
  for (const [name, field] of Object.entries(dossier.fields)) {
    if (field.status !== "contested" || field.value === null) continue;
    const values = [...new Set(field.candidates.map((candidate) => formatValue(name, candidate.value)))];
    items.push({ domain: dossier.domain, name, field, values });
  }
  return items;
}

function renderItem(item) {
  const row = document.createElement("li");
  row.className = "contested-item";
  row.dataset.testid = `contested-item-${item.domain}-${item.name}`;
  row.dataset.value = String(item.field.value);

  const title = document.createElement("p");
  title.className = "contested-title";
  title.textContent = `${item.domain} · ${FIELD_LABELS[item.name] || item.name} (${item.name})`;

  const values = document.createElement("p");
  values.className = "contested-values";
  values.textContent = `Values found: ${item.values.join("; ")}`;

  const selected = document.createElement("p");
  selected.className = "contested-selected";
  selected.textContent = `Selected: ${formatValue(item.name, item.field.value)}`;

  const link = document.createElement("a");
  link.href = `/dossiers/${encodeURIComponent(item.domain)}/evidence`;
  link.textContent = "See the evidence";

  row.append(title, values, selected, link);
  return row;
}

async function read() {
  const seq = reads.start();
  try {
    const listing = await allDossiers();
    if (!reads.accept(seq)) return;
    if (listing.result) {
      handleFailure(listing.result);
      return;
    }
    const sorted = [...listing.summaries].sort((a, b) => a.domain.localeCompare(b.domain));
    const details = await Promise.all(sorted.map((summary) => call(`/dossiers/${encodeURIComponent(summary.domain)}`)));
    if (!reads.accept(seq)) return;
    const failed = details.find((result) => result.status !== 200);
    if (failed) {
      handleFailure(failed);
      return;
    }
    const items = details.flatMap((result) => contestedItems(result.data));
    authBox.hidden = true;
    list.replaceChildren(...items.map(renderItem));
    list.hidden = items.length === 0;
    emptyBox.hidden = items.length > 0;
    statusLine.textContent = "";
  } catch (error) {
    if (!reads.accept(seq)) return;
    statusLine.textContent = error instanceof NetworkError
      ? "Could not reach the service. Reload to try again."
      : "Could not load contested fields.";
  }
}

function handleFailure(result) {
  if (result.status === 401) {
    clearSession();
    authBox.hidden = false;
    statusLine.textContent = "";
    return;
  }
  statusLine.textContent = errorMessage(result, "Could not load contested fields.");
}

read();
