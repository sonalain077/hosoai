import type { Source } from "./types";

/** "26/10/2026" — the date the official page was fetched. */
export function formatRetrievedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getUTCFullYear()}`;
}

/** Name of the portal a source comes from, falling back to its host name. */
export function sourceName(source: Source): string {
  if (source.publisher) return source.publisher;
  try {
    return new URL(source.url).hostname;
  } catch {
    return source.url;
  }
}

/** True when an item cites a different page than the procedure itself. */
export function citesOtherPage(item: Source, page: Source): boolean {
  return item.url !== page.url;
}

/** Steps on the portals start with "Bước 1:", which we already show as the list number. */
export function stripStepPrefix(text: string): string {
  return text.replace(/^\s*Bước\s*\d+\s*[:.\-–]\s*/i, "");
}
