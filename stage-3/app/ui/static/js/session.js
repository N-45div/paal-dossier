// The signed-in session lives in localStorage so it survives reloads and export/import upgrades.
const KEY = "dossier.session.v1";

export function loadSession() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    return session && typeof session.token === "string" ? session : null;
  } catch (_error) {
    return null;
  }
}

export function saveSession(session) {
  window.localStorage.setItem(KEY, JSON.stringify({
    token: session.token,
    user_id: session.user_id,
    display_name: session.display_name,
  }));
}

export function clearSession() {
  window.localStorage.removeItem(KEY);
}
