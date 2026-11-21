// People-first formatting of API values. Raw identifiers stay in data attributes.
const MONEY = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
});
const WHEN = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium", timeStyle: "short", timeZone: "UTC",
});

export const FIELD_LABELS = {
  legal_name: "Legal name",
  hq_city: "Headquarters",
  ceo: "CEO",
  founded_year: "Founded",
  headcount_range: "Headcount",
  funding_total: "Total funding",
};

// The six stage-2 fields that the stage-2 screens test by id (Rul-S3-5). `executives`, the seventh
// field of stage 3, is not one of them and is not shown by these screens.
export function sixFields(fields) {
  return Object.entries(fields).filter(([name]) => name in FIELD_LABELS);
}

export const STATE_LABELS = { building: "Building", ready: "Ready", failed: "Failed" };
export const STATUS_LABELS = { known: "Known", unknown: "Unknown", contested: "Contested" };

// The value as text: strings unchanged; integers formatted per field.
export function formatValue(field, value) {
  if (field === "funding_total" && Number.isInteger(value)) return MONEY.format(value);
  return String(value);
}

export function formatWhen(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : WHEN.format(date);
}

export function providerLabel(provider) {
  const text = String(provider || "");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Unknown source";
}
