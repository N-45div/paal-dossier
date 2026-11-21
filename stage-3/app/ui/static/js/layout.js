// Shared chrome: reflects the session on every screen and handles log out.
import { clearSession, loadSession } from "/static/js/session.js";

export function renderSession() {
  const session = loadSession();
  document.body.dataset.session = session ? "in" : "out";
  const name = document.querySelector('[data-testid="current-user"]');
  if (name) name.textContent = session ? session.display_name : "";
  return session;
}

renderSession();

const logout = document.querySelector('[data-testid="logout-button"]');
if (logout) {
  logout.addEventListener("click", () => {
    // The API has no logout endpoint; the browser forgets its token.
    clearSession();
    window.location.assign("/");
  });
}
