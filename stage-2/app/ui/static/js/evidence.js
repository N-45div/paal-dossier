// Evidence for one dossier: every candidate of every field, in the API's candidate order.
import { call, errorMessage, NetworkError } from "/static/js/api.js";
import { clearSession } from "/static/js/session.js";
import { createLatestReads } from "/static/js/latest.js";
import { FIELD_LABELS, formatValue, formatWhen, providerLabel } from "/static/js/format.js";

const root = document.getElementById("evidence-root");
const domain = root.dataset.domain;
const endpoint = `/dossiers/${encodeURIComponent(domain)}`;
const statusLine = document.getElementById("evidence-status");
const fieldsBox = document.getElementById("evidence-fields");
const authBox = document.getElementById("evidence-auth");
const notFound = root.querySelector(".not-found");
const reads = createLatestReads();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCandidate(field, candidate, index) {
  const item = el("li", "candidate");
  item.dataset.testid = `candidate-${field}-${index + 1}`;
  item.dataset.value = String(candidate.value);
  item.dataset.provider = candidate.provider;
  item.dataset.kind = candidate.kind || "";
  item.dataset.url = candidate.url;
  item.dataset.publishedAt = candidate.published_at || "";
  item.dataset.selected = candidate.selected ? "true" : "false";

  const head = el("div", "candidate-head");
  head.append(el("span", "candidate-value", formatValue(field, candidate.value)));
  head.append(el("span", candidate.selected ? "badge known" : "badge unknown",
    candidate.selected ? "Selected" : "Not selected"));
  const quote = el("blockquote");
  quote.append(el("p", "", candidate.excerpt));
  const meta = el("p", "source");
  meta.append(el("span", "provider", providerLabel(candidate.provider)));
  if (candidate.kind) meta.append(` · ${candidate.kind}`);
  if (candidate.published_at) meta.append(` · published ${formatWhen(candidate.published_at)}`);
  const link = el("a", "", candidate.url);
  link.href = candidate.url;
  link.rel = "noopener noreferrer";
  meta.append(" · ", link);
  item.append(head, quote, meta);
  return item;
}

function renderField(name, field) {
  const block = el("article", "field");
  block.dataset.field = name;
  const title = el("div", "field-title");
  title.append(el("h2", "", FIELD_LABELS[name] || name));
  block.append(title);

  const list = el("ul", "citations");
  list.dataset.testid = `evidence-${name}`;
  if (field.candidates.length === 0) {
    const empty = el("li", "field-empty", "No source gives a value for this field.");
    empty.dataset.testid = `evidence-empty-${name}`;
    list.append(empty);
  } else {
    field.candidates.forEach((candidate, index) => {
      list.append(renderCandidate(name, candidate, index));
    });
  }
  block.append(list);
  return block;
}

function renderFields(dossier) {
  fieldsBox.replaceChildren(
    ...Object.entries(dossier.fields).map(([name, field]) => renderField(name, field)),
  );
}

// Reading the API's dossier; the screen shows the last ready data it was given.
async function read() {
  const seq = reads.start();
  let result;
  try {
    result = await call(endpoint);
  } catch (error) {
    if (!reads.accept(seq)) return;
    statusLine.textContent = error instanceof NetworkError
      ? "Could not reach the service. Reload to try again."
      : "Could not load evidence.";
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
    notFound.hidden = false;
    fieldsBox.replaceChildren();
    statusLine.textContent = "";
    return;
  }
  if (result.status !== 200) {
    statusLine.textContent = errorMessage(result, "Could not load evidence.");
    return;
  }
  notFound.hidden = true;
  authBox.hidden = true;
  statusLine.textContent = "";
  renderFields(result.data);
}

read();
