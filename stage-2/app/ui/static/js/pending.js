// A research or refresh request whose outcome is unknown keeps its key and body, so the retry
// is the same request (spec §7, Rul-S2-7). A response (any status) ends the pending request.
export function newKey() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function createPending() {
  let current = null;
  return {
    // The pending request for this body, reusing its key when the body is unchanged.
    forBody(body) {
      const same = current && JSON.stringify(current.body) === JSON.stringify(body);
      if (!same) current = { key: newKey(), body };
      return current;
    },
    uncertain() {
      return current !== null;
    },
    clear() {
      current = null;
    },
  };
}
