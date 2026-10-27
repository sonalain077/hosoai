import { describe, expect, test } from "vitest";

import {
  citesOtherPage,
  formatRetrievedAt,
  groupDossier,
  sourceName,
  stripStepPrefix,
} from "./format";
import type { Source } from "./types";

const src = (over: Partial<Source> = {}): Source => ({
  url: "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497",
  title: "Cấp hộ chiếu phổ thông",
  document_number: "1.001456",
  publisher: "Cổng Dịch vụ công - Bộ Công an",
  retrieved_at: "2026-10-26T10:42:13.837193Z",
  ...over,
});

describe("format", () => {
  test("retrieved date is shown day first", () => {
    expect(formatRetrievedAt("2026-10-26T10:42:13.837193Z")).toBe("26/10/2026");
  });

  test("source name prefers publisher, then host", () => {
    expect(sourceName(src())).toBe("Cổng Dịch vụ công - Bộ Công an");
    expect(sourceName(src({ publisher: null }))).toBe("dichvucong.bocongan.gov.vn");
  });

  test("detects items citing another page", () => {
    expect(citesOtherPage(src(), src())).toBe(false);
    expect(citesOtherPage(src({ url: "https://x.gov.vn/a" }), src())).toBe(true);
  });

  test("strips the portal's own step numbering", () => {
    expect(stripStepPrefix("Bước 1: Chuẩn bị hồ sơ.")).toBe("Chuẩn bị hồ sơ.");
    expect(stripStepPrefix("Nộp hồ sơ")).toBe("Nộp hồ sơ");
  });
});

describe("groupDossier", () => {
  test("keeps every document, grouped by status, in order", () => {
    const docs = [
      { id: "d1", status: "needed" as const },
      { id: "d2", status: "not_needed" as const },
      { id: "d3", status: "unsure" as const },
      { id: "d4", status: "needed" as const },
    ];
    const g = groupDossier(docs);
    expect(g.needed.map((d) => d.id)).toEqual(["d1", "d4"]);
    expect(g.unsure.map((d) => d.id)).toEqual(["d3"]);
    expect(g.notNeeded.map((d) => d.id)).toEqual(["d2"]);
    expect(g.needed.length + g.unsure.length + g.notNeeded.length).toBe(docs.length);
  });
});
