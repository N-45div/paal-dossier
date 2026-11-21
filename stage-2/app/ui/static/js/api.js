// JSON API client. Every call asks for JSON explicitly, so the shared dossier route answers JSON.
import { loadSession } from "/static/js/session.js";

export class NetworkError extends Error {}

// Returns { status, data } for any HTTP response. Throws NetworkError when no response
// arrives (the request may still have taken effect).
export async function call(path, { method = "GET", body, key, auth = true } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key !== undefined) headers["Idempotency-Key"] = key;
  if (auth) {
    const session = loadSession();
    if (session) headers.Authorization = `Bearer ${session.token}`;
  }
  let response;
  let text;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    text = await response.text();
  } catch (_error) {
    throw new NetworkError("no response");
  }
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_error) {
    data = null;
  }
  return { status: response.status, data };
}

// The server's message for an error response, or a fallback.
export function errorMessage(result, fallback) {
  const message = result && result.data && result.data.error && result.data.error.message;
  return typeof message === "string" && message ? message : fallback;
}
