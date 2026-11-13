export interface Evidence {
  text_start: number | null;
  text_end: number | null;
  text_snippet: string | null;
}

/** Where a review item's evidence sits in the email text, or null when it cannot be found.
 *  The stored offsets are trusted only when they select exactly the stored snippet, because
 *  the console shows a preview that may not be the text the offsets were counted in. */
export function findEvidence(text: string, item: Evidence): { start: number; end: number } | null {
  const { text_start: start, text_end: end, text_snippet: snippet } = item;
  if (start !== null && end !== null && start < end && (snippet === null || text.slice(start, end) === snippet)) {
    return { start, end };
  }
  if (!snippet) return null;
  const at = text.indexOf(snippet);
  return at === -1 ? null : { start: at, end: at + snippet.length };
}
