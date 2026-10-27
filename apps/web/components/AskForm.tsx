"use client";

import Link from "next/link";
import { useState } from "react";

import { ask } from "@/lib/api";
import type { MatchResult } from "@/lib/types";

const EXAMPLES = [
  "Tôi cần làm hộ chiếu",
  "Tôi bị mất căn cước",
  "Con tôi mới sinh",
  "My visa is about to expire",
];

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; result: MatchResult }
  | { kind: "error" };

export function AskForm() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function submit(text: string) {
    const q = text.trim();
    if (!q) return;
    setState({ kind: "loading" });
    try {
      setState({ kind: "done", result: await ask(q) });
    } catch {
      setState({ kind: "error" });
    }
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit(query);
        }}
        className="rounded-sm bg-sheet px-5 pb-5 pt-4 shadow-[0_1px_0_var(--rule)] sm:px-7"
      >
        <label htmlFor="query" className="block font-medium text-muted">
          Nội dung cần làm
        </label>
        <textarea
          id="query"
          rows={2}
          maxLength={1000}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit(query);
            }
          }}
          placeholder="Ví dụ: tôi muốn đăng ký tạm trú cho phòng mới thuê"
          className="form-lines w-full resize-none bg-transparent text-xl text-pen placeholder:text-muted/60 focus:outline-none sm:text-2xl"
        />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">Viết bằng tiếng Việt, English, hay ngôn ngữ khác.</p>
          <button
            type="submit"
            disabled={state.kind === "loading" || !query.trim()}
            className="rounded-sm bg-pen px-5 py-2.5 font-semibold text-sheet disabled:opacity-40"
          >
            {state.kind === "loading" ? "Đang tìm…" : "Tìm thủ tục"}
          </button>
        </div>
      </form>

      <div className="mt-4 flex flex-wrap gap-2" aria-label="Ví dụ">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setQuery(ex);
              void submit(ex);
            }}
            className="rounded-full border border-rule px-3 py-1 text-sm text-muted hover:border-pen hover:text-pen"
          >
            {ex}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="mt-10">
        {state.kind === "error" && (
          <p className="border-l-4 border-stamp pl-4">
            Không kết nối được máy chủ. Kiểm tra API đang chạy rồi thử lại.
          </p>
        )}
        {state.kind === "done" && <Result result={state.result} />}
      </div>
    </div>
  );
}

function Result({ result }: { result: MatchResult }) {
  if (result.status === "not_found") {
    return (
      <div className="border-l-4 border-stamp pl-4">
        <p className="font-semibold text-stamp">Chưa có trong nguồn chính thức</p>
        <p className="mt-1 max-w-prose">
          Chúng tôi không tìm thấy thủ tục này trong các trang chính thức hiện có, nên sẽ không
          đoán. Thử diễn đạt khác, hoặc chọn trong danh sách bên dưới.
        </p>
      </div>
    );
  }
  return (
    <div>
      <p className="font-medium text-muted">
        {result.status === "matched"
          ? "Thủ tục phù hợp với bạn"
          : "Có thể là một trong các thủ tục sau. Chọn trường hợp của bạn:"}
      </p>
      <ul className="mt-3 divide-y divide-rule border-y border-rule">
        {result.candidates.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/procedure/${c.slug}`}
              className="group block py-4 hover:bg-sheet sm:px-2"
            >
              <span className="font-serif text-lg leading-snug group-hover:text-pen">
                {c.title}
              </span>
              <span className="mt-1 block text-sm text-muted">
                {c.label_en && <>{c.label_en}. </>}
                {c.national_code && <>Mã {c.national_code}</>}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
