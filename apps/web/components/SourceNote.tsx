import { formatRetrievedAt, sourceName } from "@/lib/format";
import type { Source } from "@/lib/types";

/** Citation line under a section: which official page, which code, when we read it. */
export function SourceNote({ source }: { source: Source }) {
  return (
    <p className="mt-3 text-sm text-muted">
      <span className="font-semibold text-stamp">Nguồn:</span>{" "}
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="underline decoration-rule underline-offset-4 hover:decoration-stamp"
      >
        {sourceName(source)}
      </a>
      {source.document_number && <>, mã thủ tục {source.document_number}</>}
      <>, đọc ngày {formatRetrievedAt(source.retrieved_at)}</>
    </p>
  );
}

/** Small marker for an item whose source differs from the page-level source. */
export function ItemSource({ source }: { source: Source }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-2 whitespace-nowrap text-xs font-semibold text-stamp underline underline-offset-2"
    >
      nguồn riêng
    </a>
  );
}
