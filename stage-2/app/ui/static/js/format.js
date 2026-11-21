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
