// Signup and login: store the session on success, show one error message otherwise.
import { call, errorMessage, NetworkError } from "/static/js/api.js";
import { saveSession } from "/static/js/session.js";

const form = document.getElementById("auth-form");
const errorBox = document.querySelector('[data-testid="auth-error"]');
const isSignup = Boolean(document.querySelector('[data-testid="signup-submit"]'));

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const data = new FormData(form);
  const body = isSignup
    ? {
        email: data.get("email"),
        password: data.get("password"),
        display_name: data.get("display_name"),
      }
    : { email: data.get("email"), password: data.get("password") };
  const path = isSignup ? "/auth/signup" : "/auth/login";
  try {
    const result = await call(path, { method: "POST", body, auth: false });
    if (result.status === 200 || result.status === 201) {
      saveSession({
        token: result.data.token,
        user_id: result.data.user_id,
        display_name: result.data.display_name,
      });
      window.location.assign("/");
      return;
    }
    showError(errorMessage(result, "Something went wrong. Try again."));
  } catch (error) {
    showError(error instanceof NetworkError
      ? "No response from the service. Try again."
      : "Something went wrong. Try again.");
  }
});
