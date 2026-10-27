"use client";

import Link from "next/link";
import { useState } from "react";

import { formHref } from "@/lib/api";
import { citesOtherPage, groupDossier } from "@/lib/format";
import type { Dossier, DossierDocument, Source } from "@/lib/types";

import { ItemSource, SourceNote } from "./SourceNote";

/** The personal checklist the agent built. Every document stays visible, grouped by status. */
export function DossierView({ dossier }: { dossier: Dossier }) {
  const p = dossier.procedure;
  const g = groupDossier(dossier.documents);
  const [done, setDone] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <article>
      <p className="text-muted">Hồ sơ của bạn cho thủ tục</p>
      <h2 className="mt-1 font-serif text-2xl font-semibold leading-snug sm:text-3xl">{p.title}</h2>
      <SourceNote source={p.source} />

      {dossier.forms.length > 0 && (
        <section className="mt-8 rounded-sm bg-sheet px-5 py-4 shadow-[0_1px_0_var(--rule)]">
          <h3 className="font-semibold">Tờ khai cần điền</h3>
          <p className="text-sm text-muted">
            Điền sẵn từ hồ sơ cá nhân của bạn. Bạn kiểm tra rồi tải về để in, ký và nộp.
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {dossier.forms.map((f) => (
              <li key={f.id}>
                <Link
                  href={formHref(f.id, p.slug)}
                  className="inline-block rounded-sm bg-pen px-4 py-2 font-semibold text-sheet"
                >
                  Điền tờ khai {f.code}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Group
        title="Cần chuẩn bị"
        hint={`Đã chuẩn bị ${g.needed.filter((d) => done.has(d.id)).length}/${g.needed.length}`}
        docs={g.needed}
        page={p.source}
        done={done}
        onToggle={toggle}
      />
      <Group
        title="Kiểm tra lại với trường hợp của bạn"
        hint="Trang chính thức có liệt kê, nhưng chưa rõ có áp dụng cho bạn không."
        docs={g.unsure}
        page={p.source}
        done={done}
        onToggle={toggle}
      />
      {g.notNeeded.length > 0 && (
        <details className="mt-10">
          <summary className="cursor-pointer text-lg font-semibold">
            Có thể không cần ({g.notNeeded.length})
          </summary>
          <ul className="mt-3 divide-y divide-rule">
            {g.notNeeded.map((d) => (
              <li key={d.id} className="py-3 text-muted">
                <p className="font-serif leading-relaxed">{d.document.name}</p>
                <Because doc={d} />
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="mt-10">
        <Link
          href={`/procedure/${p.slug}`}
          className="font-semibold text-pen underline underline-offset-4"
        >
          Xem các bước, thời hạn, lệ phí và biểu mẫu
        </Link>
      </p>
    </article>
  );
}

function Group({
  title,
  hint,
  docs,
  page,
  done,
  onToggle,
}: {
  title: string;
  hint: string;
  docs: DossierDocument[];
  page: Source;
  done: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (docs.length === 0) return null;
  return (
    <section className="mt-10">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted">{hint}</p>
      <ul className="mt-2 divide-y divide-rule">
        {docs.map((d) => (
          <li key={d.id} className="flex gap-3 py-3">
            <input
              id={`dossier-${d.id}`}
              type="checkbox"
              checked={done.has(d.id)}
              onChange={() => onToggle(d.id)}
              className="mt-1.5 size-5 shrink-0 accent-[var(--pen)]"
            />
            <label htmlFor={`dossier-${d.id}`} className="cursor-pointer">
              <span
                className={`font-serif leading-relaxed ${done.has(d.id) ? "text-muted line-through" : ""}`}
              >
                {d.document.name}
              </span>
              {(d.document.quantity || d.document.form_name) && (
                <span className="mt-1 block text-sm text-muted">
                  {d.document.form_name && <>Mẫu: {d.document.form_name}. </>}
                  {d.document.quantity}
                </span>
              )}
              {citesOtherPage(d.document.source, page) && <ItemSource source={d.document.source} />}
              <Because doc={d} />
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Why the agent placed this document here: the user's own words, quoted. */
function Because({ doc }: { doc: DossierDocument }) {
  if (doc.because.length === 0) return null;
  return (
    <span className="mt-1 block text-sm text-muted">
      Vì bạn đã nói:{" "}
      {doc.because.map((b, i) => (
        <span key={b.number}>
          {i > 0 && "; "}
          <span className="text-pen">“{b.answer}”</span>
        </span>
      ))}
    </span>
  );
}
