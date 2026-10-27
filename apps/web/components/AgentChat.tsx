"use client";

import { useRef, useState } from "react";

import { agentAnswer, agentStart } from "@/lib/api";
import type { AgentQuestion, AgentReply } from "@/lib/types";

import { DossierView } from "./DossierView";

const EXAMPLES = [
  "Tôi cần làm hộ chiếu cho con 10 tuổi",
  "Tôi bị mất căn cước",
  "Tôi muốn đăng ký tạm trú ở phòng trọ mới",
  "My visa is about to expire",
];

type Turn = { question: AgentQuestion; answer: string };

export function AgentChat() {
  const [query, setQuery] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [reply, setReply] = useState<AgentReply | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const pendingRef = useRef<HTMLDivElement>(null);

  async function call(fn: () => Promise<AgentReply>) {
    setBusy(true);
    setError(false);
    try {
      const r = await fn();
      setReply(r);
      requestAnimationFrame(() => pendingRef.current?.focus());
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  function begin(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setAsked(q);
    setTurns([]);
    setReply(null);
    void call(() => agentStart(q));
  }

  function respond(answer: string) {
    const a = answer.trim();
    if (!a || !reply?.question || busy) return;
    setTurns((t) => [...t, { question: reply.question!, answer: a }]);
    const id = reply.session_id;
    void call(() => agentAnswer(id, a));
  }

  function reset() {
    setQuery("");
    setAsked(null);
    setTurns([]);
    setReply(null);
    setError(false);
  }

  if (asked === null) {
    return (
      <div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            begin(query);
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
                begin(query);
              }
            }}
            placeholder="Ví dụ: tôi muốn đăng ký tạm trú cho phòng mới thuê"
            className="form-lines w-full resize-none bg-transparent text-xl text-pen placeholder:text-muted/60 focus:outline-none sm:text-2xl"
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">Viết bằng tiếng Việt, English, hay ngôn ngữ khác.</p>
            <button
              type="submit"
              disabled={!query.trim()}
              className="rounded-sm bg-pen px-5 py-2.5 font-semibold text-sheet disabled:opacity-40"
            >
              Bắt đầu
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
                begin(ex);
              }}
              className="rounded-full border border-rule px-3 py-1 text-sm text-muted hover:border-pen hover:text-pen"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    );
  }

  const pending = reply?.type === "question" ? reply.question : null;

  return (
    <div>
      <ol className="space-y-6">
        <Filled label="Yêu cầu của bạn" value={asked} />
        {turns.map((t, i) => (
          <Filled key={i} label={t.question.text} value={t.answer} />
        ))}
      </ol>

      <div ref={pendingRef} tabIndex={-1} aria-live="polite" className="mt-8 focus:outline-none">
        {busy && <p className="text-muted">Đang đọc trang chính thức…</p>}
        {error && (
          <p className="border-l-4 border-stamp pl-4">
            Không kết nối được máy chủ. Kiểm tra API đang chạy rồi thử lại.
          </p>
        )}
        {!busy && pending && <PendingQuestion q={pending} onAnswer={respond} />}
        {!busy && reply?.type === "not_found" && (
          <div className="border-l-4 border-stamp pl-4">
            <p className="font-semibold text-stamp">Chưa có trong nguồn chính thức</p>
            <p className="mt-1 max-w-prose">
              Chúng tôi không tìm thấy thủ tục này trong các trang chính thức hiện có, nên sẽ
              không đoán. Thử diễn đạt khác, hoặc chọn trong danh sách bên dưới.
            </p>
          </div>
        )}
        {!busy && reply?.type === "dossier" && reply.dossier && (
          <DossierView dossier={reply.dossier} />
        )}
      </div>

      <button
        type="button"
        onClick={reset}
        className="mt-10 text-sm font-semibold text-muted underline underline-offset-4 hover:text-pen"
      >
        Bắt đầu lại
      </button>
    </div>
  );
}

/** A question already answered, shown like a filled-in line on a paper form. */
function Filled({ label, value }: { label: string; value: string }) {
  return (
    <li>
      <p className="text-muted">{label}</p>
      <p className="form-lines text-xl text-pen">{value}</p>
    </li>
  );
}

function PendingQuestion({ q, onAnswer }: { q: AgentQuestion; onAnswer: (a: string) => void }) {
  const [other, setOther] = useState("");
  return (
    <div className="rounded-sm bg-sheet px-5 py-5 shadow-[0_1px_0_var(--rule)] sm:px-7">
      <p className="text-xl font-semibold leading-snug">{q.text}</p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {q.options.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => onAnswer(o)}
            className={`rounded-sm border border-pen px-4 py-2 text-left text-pen hover:bg-pen hover:text-sheet ${q.kind === "choose_procedure" ? "font-serif" : "font-medium"}`}
          >
            {o}
          </button>
        ))}
      </div>
      {q.kind === "case" && (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onAnswer(other);
          }}
        >
          <label htmlFor="other" className="sr-only">
            Câu trả lời khác
          </label>
          <input
            id="other"
            value={other}
            maxLength={500}
            onChange={(e) => setOther(e.target.value)}
            placeholder="Hoặc tự trả lời…"
            className="form-lines min-w-0 flex-1 bg-transparent text-pen placeholder:text-muted/60 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!other.trim()}
            className="font-semibold text-pen disabled:opacity-40"
          >
            Gửi
          </button>
        </form>
      )}
      {q.about.length > 0 && (
        <div className="mt-5 border-t border-rule pt-3 text-sm text-muted">
          <p>Câu hỏi này giúp xác định bạn có cần:</p>
          <ul className="mt-1 list-disc pl-5 font-serif">
            {q.about.map((d) => (
              <li key={d.id} className="line-clamp-2">
                {d.name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
