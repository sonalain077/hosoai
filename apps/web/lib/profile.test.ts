import { expect, test } from "vitest";

import { filledCount, normalizeProfile, PROFILE_FIELDS } from "./profile";
import type { Profile } from "./types";

const empty = Object.fromEntries(PROFILE_FIELDS.map((f) => [f.key, null])) as Profile;

test("blank strings are saved as null, others trimmed", () => {
  const p = normalizeProfile({ ...empty, full_name: "  Nguyễn Văn Thử ", phone: "   " });
  expect(p.full_name).toBe("Nguyễn Văn Thử");
  expect(p.phone).toBeNull();
});

test("counts filled fields", () => {
  expect(filledCount(empty)).toBe(0);
  expect(filledCount({ ...empty, full_name: "A", sex: "Nam" })).toBe(2);
});

test("every profile key appears once in the form", () => {
  const keys = PROFILE_FIELDS.map((f) => f.key);
  expect(new Set(keys).size).toBe(keys.length);
  expect(keys.length).toBe(Object.keys(empty).length);
});
