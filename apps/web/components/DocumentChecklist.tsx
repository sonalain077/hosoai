"use client";

import { useState } from "react";

import { citesOtherPage } from "@/lib/format";
import type { RequiredDocument, Source } from "@/lib/types";

import { ItemSource } from "./SourceNote";

/** Documents to bring. Ticking is only a personal reminder; nothing is saved or sent. */
export function DocumentChecklist({ docs, page }: { docs: RequiredDocument[]; page: Source }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <>
      <p className="text-sm text-muted">
        Đã chuẩn bị {done.size}/{docs.length}
      </p>
      <ul className="mt-2 divide-y divide-rule">
        {docs.map((d, i) => (
          <li key={i} className="flex gap-3 py-3">
            <input
              id={`doc-${i}`}
              type="checkbox"
              checked={done.has(i)}
              onChange={() => toggle(i)}
              className="mt-1.5 size-5 shrink-0 accent-[var(--pen)]"
            />
            <label htmlFor={`doc-${i}`} className="cursor-pointer">
              <span
                className={`font-serif leading-relaxed ${done.has(i) ? "text-muted line-through" : ""}`}
              >
                {d.name}
              </span>
              {(d.quantity || d.form_name) && (
                <span className="mt-1 block text-sm text-muted">
                  {d.form_name && <>Mẫu: {d.form_name}. </>}
                  {d.quantity}
                </span>
              )}
              {citesOtherPage(d.source, page) && <ItemSource source={d.source} />}
            </label>
          </li>
        ))}
      </ul>
    </>
  );
}
