import { describe, expect, it } from "vitest";

import { findEvidence } from "./evidence";

const text = "SQ856/13NOV SIN P4 J30 Y176";

describe("findEvidence", () => {
  it("uses the stored offsets when they select the snippet", () => {
    expect(findEvidence(text, { text_start: 23, text_end: 27, text_snippet: "Y176" })).toEqual({ start: 23, end: 27 });
  });

  it("falls back to searching for the snippet when the offsets point elsewhere", () => {
    expect(findEvidence(text, { text_start: 0, text_end: 4, text_snippet: "Y176" })).toEqual({ start: 23, end: 27 });
  });

  it("finds the snippet when there are no offsets", () => {
    expect(findEvidence(text, { text_start: null, text_end: null, text_snippet: "J30" })).toEqual({ start: 19, end: 22 });
  });

  it("returns null when the evidence is not in the text", () => {
    expect(findEvidence(text, { text_start: null, text_end: null, text_snippet: "TTL 240" })).toBeNull();
    expect(findEvidence(text, { text_start: null, text_end: null, text_snippet: null })).toBeNull();
  });
});
