// R4.41: the screens treat `investors` as they treat `executives`: no data-testid of stage 2, and
import { test } from "node:test";
import assert from "node:assert/strict";
import { FIELD_LABELS, sixFields } from "../../app/ui/static/js/format.js";

const contestedInvestors = {
  legal_name: { status: "known", value: "Acme Robotics, Inc." },
  investors: {
    status: "contested",
    value: ["Bluebird Capital"],
    candidates: [{ value: "Bluebird Capital" }, { value: "Northwind Ventures" }],
  },
};

test("R4.41: investors is not one of the six screen fields, even when contested", () => {
  assert.equal("investors" in FIELD_LABELS, false);
  const names = sixFields(contestedInvestors).map(([name]) => name);
  assert.deepEqual(names, ["legal_name"]);
});

test("R4.41: a dossier whose only contested field is investors lists no contested field", () => {
  const onlyInvestors = { investors: contestedInvestors.investors };
  assert.deepEqual(sixFields(onlyInvestors), []);
});
