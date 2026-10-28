"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiError, formHref, learnForm } from "@/lib/api";
import type { LearnResult, OfficialForm } from "@/lib/types";

type RowState =
  | { kind: "idle" }
  | { kind: "learning" }
  | { kind: "learned"; result: LearnResult }
  | { kind: "error"; message: string };

/** Official forms of a procedure. Unknown ones can be read by the form-learning agent. */
export function OfficialForms({ slug, forms }: { slug: string; forms: OfficialForm[] }) {
  const [rows, setRows] = useState<Record<number, RowState>>({});
  const set = (i: number, st: RowState) => setRows((r) => ({ ...r, [i]: st }));

  async function learn(i: number) {
    set(i, { kind: "learning" });
    try {
      set(i, { kind: "learned", result: await learnForm(slug, i) });
    } catch (e) {
      set(i, {
        kind: "error",
        message: e instanceof ApiError ? e.message : "Không kết nối được máy chủ.",
      });
    }
  }

  return (
    <ul className="divide-y divide-rule border-y border-rule">
      {forms.map((f) => {
        const st = rows[f.index] ?? { kind: "idle" };
        const formId = st.kind === "learned" ? st.result.form.id : f.form_id;
        const draft = st.kind === "learned" || f.status === "draft";
        return (
          <li key={f.index} className="py-4">
            <a
              href={f.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-serif underline decoration-rule underline-offset-4 hover:decoration-stamp"
            >
              {f.label}
            </a>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {formId ? (
                <Link
                  href={formHref(formId, slug)}
                  className="rounded-sm bg-pen px-4 py-2 font-semibold text-sheet"
                >
                  Điền tờ khai này
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => void learn(f.index)}
                  disabled={st.kind === "learning"}
                  className="rounded-sm border border-pen px-4 py-2 font-semibold text-pen disabled:opacity-50"
                >
                  {st.kind === "learning"
                    ? "Trợ lý đang đọc tờ khai…"
                    : "Để trợ lý AI đọc tờ khai này"}
                </button>
              )}
              {draft && formId && (
                <span className="text-sm text-stamp">Bản nháp do AI đọc, cần kiểm tra kỹ</span>
              )}
            </div>
            <div aria-live="polite" className="mt-2 text-sm text-muted">
              {st.kind === "learning" && (
                <p>
                  Tải tệp chính thức, tìm các ô cần điền, rồi kiểm tra từng ô trên tệp gốc. Mất
                  khoảng 30 đến 90 giây.
                </p>
              )}
              {st.kind === "learned" && (
                <p>
                  Đã nhận diện {st.result.report.accepted.length} ô (trong{" "}
                  {st.result.report.candidates} chỗ có thể viết), mỗi ô đã được kiểm tra vị trí
                  trên tệp gốc qua {st.result.report.rounds} lượt.
                </p>
              )}
              {st.kind === "error" && (
                <p className="text-stamp">Không đọc được tờ khai này: {st.message}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
