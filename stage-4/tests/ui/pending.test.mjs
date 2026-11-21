// Uncertain outcomes keep the key and body (spec Refresh and competing clients, Rul-S2-7).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createPending } from "../../app/ui/static/js/pending.js";

test("the same body reuses the same key (retry after a lost response)", () => {
  const pending = createPending();
  const first = pending.forBody({ domain: "acme-robotics.test" });
  const retry = pending.forBody({ domain: "acme-robotics.test" });
  assert.equal(retry.key, first.key);
  assert.equal(pending.uncertain(), true);
});

test("a different body gets a new key", () => {
  const pending = createPending();
  const first = pending.forBody({ domain: "acme-robotics.test" });
  const other = pending.forBody({ domain: "other.test" });
  assert.notEqual(other.key, first.key);
});

test("clear ends the pending request and the next request is a first use", () => {
  const pending = createPending();
  const first = pending.forBody(null);
  pending.clear();
  assert.equal(pending.uncertain(), false);
  assert.notEqual(pending.forBody(null).key, first.key);
});

test("a null body (refresh) is compared as the same body", () => {
  const pending = createPending();
  assert.equal(pending.forBody(null).key, pending.forBody(null).key);
});
