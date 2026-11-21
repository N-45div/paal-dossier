// Latest read wins (spec Refresh and competing clients). Run: node --test tests/ui
import { test } from "node:test";
import assert from "node:assert/strict";
import { createLatestReads } from "../../app/ui/static/js/latest.js";

test("a later read that has applied blocks an earlier read arriving late", () => {
  const reads = createLatestReads();
  const first = reads.start();
  const second = reads.start();
  assert.equal(reads.accept(second), true);
  assert.equal(reads.accept(first), false, "delayed earlier read must not overwrite");
});

test("reads applied in issue order all apply", () => {
  const reads = createLatestReads();
  const a = reads.start();
  assert.equal(reads.accept(a), true);
  const b = reads.start();
  assert.equal(reads.accept(b), true);
});

test("a read issued after another has applied still applies", () => {
  const reads = createLatestReads();
  const a = reads.start();
  const b = reads.start();
  reads.accept(b);
  const c = reads.start();
  assert.equal(reads.accept(c), true);
  assert.equal(reads.accept(a), false);
});
