"use client";

import { useEffect, useState } from "react";

import { blankPageUrl, fillForm, previewPage } from "@/lib/api";
import type { FormDetail } from "@/lib/types";

import { SourceNote } from "./SourceNote";

/** The real form on the left, its fields in plain language on the right. */
export function FormFiller({ detail }: { detail: FormDetail }) {
  const { spec } = detail;
  const [values, setValues] = useState<Record<string, string>>(detail.values);
  const [preview, setPreview] = useState<string[] | null>(null); // image URLs, one per page
  const [stale, setStale] = useState(false);
  const pages = Array.from({ length: Math.max(1, spec.preview_pages) }, (_, i) => i);
  const [reviewed, setReviewed] = useState(false);
  const [state, setState] = useState<"idle" | "working" | "error">("idle");

  useEffect(() => () => preview?.forEach((u) => URL.revokeObjectURL(u)), [preview]);

  const set = (key: string, value: string) => {
    setValues((v) => ({ ...v, [key]: value }));
    setStale(true);
    setReviewed(false);
  };

  async function showPreview() {
    setState("working");
    try {
      const blobs = await Promise.all(pages.map((n) => previewPage(spec.id, n, values)));
      setPreview(blobs.map((b) => URL.createObjectURL(b)));
      setStale(false);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  async function download() {
    setState("working");
    try {
      const url = URL.createObjectURL(await fillForm(spec.id, values));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${spec.code}-da-dien.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  const fromProfile = spec.fields.filter((f) => f.profile_key && detail.values[f.key]).length;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-4 lg:self-start">
        <div className="space-y-3">
          {pages.map((n) => (
            // eslint-disable-next-line @next/next/no-img-element -- generated on our API, not static
            <img
              key={n}
              src={preview && !stale ? preview[n] : blankPageUrl(spec.id, n)}
              alt={`${spec.code}, trang ${n + 1}${preview && !stale ? ", bản đã điền" : ", mẫu trống"}`}
              className="w-full rounded-sm border border-rule bg-white"
            />
          ))}
        </div>
        <p className="mt-2 text-sm text-muted">
          {preview && !stale
            ? "Bản xem trước với thông tin của bạn."
            : "Mẫu trống, đúng như trên trang chính thức."}
        </p>
      </div>

      <div>
        {spec.status === "draft" && (
          <p className="mb-5 border-l-4 border-stamp bg-sheet py-3 pl-4 pr-3 text-sm">
            <span className="font-semibold text-stamp">Bản nháp do trợ lý AI đọc.</span> Các ô
            được tìm và kiểm tra vị trí tự động trên tệp chính thức, nhưng chưa có người duyệt.
            Hãy so sánh kỹ bản xem trước với mẫu gốc.
          </p>
        )}
        <p className="text-sm text-muted">
          {fromProfile > 0
            ? `${fromProfile} mục đã điền sẵn từ hồ sơ cá nhân. Kiểm tra lại từng mục.`
            : "Chưa có mục nào điền sẵn. Lưu hồ sơ cá nhân để lần sau điền nhanh hơn."}
        </p>
        <ol className="mt-4 space-y-5">
          {spec.fields.map((f) => (
            <li key={f.key}>
              <label htmlFor={`f-${f.key}`} className="block">
                <span className="font-serif">{f.label}</span>
                {f.hint && <span className="ml-2 text-sm text-muted">{f.hint}</span>}
              </label>
              <input
                id={`f-${f.key}`}
                value={values[f.key] ?? ""}
                maxLength={f.max_chars ?? 300}
                inputMode={f.mode === "boxes" ? "numeric" : undefined}
                onChange={(e) => set(f.key, e.target.value)}
                className="form-lines w-full bg-transparent text-lg text-pen focus:outline-none"
              />
            </li>
          ))}
        </ol>

        {spec.notes.length > 0 && (
          <ul className="mt-6 list-disc pl-5 text-sm text-muted">
            {spec.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}

        <div className="mt-8 border-t border-rule pt-5">
          <label className="flex cursor-pointer gap-3">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
              className="mt-1 size-5 shrink-0 accent-[var(--pen)]"
            />
            <span>Tôi đã kiểm tra từng mục và bản xem trước.</span>
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void showPreview()}
              disabled={state === "working"}
              className="rounded-sm border border-pen px-4 py-2.5 font-semibold text-pen disabled:opacity-40"
            >
              {state === "working" ? "Đang tạo…" : "Xem trước"}
            </button>
            <button
              type="button"
              onClick={() => void download()}
              disabled={!reviewed || state === "working"}
              className="rounded-sm bg-pen px-5 py-2.5 font-semibold text-sheet disabled:opacity-40"
            >
              Tải tờ khai (PDF)
            </button>
          </div>
          {state === "error" && (
            <p className="mt-3 border-l-4 border-stamp pl-4">
              Không tạo được tờ khai. Kiểm tra API đang chạy rồi thử lại.
            </p>
          )}
          <p className="mt-4 text-sm text-muted">
            Hồ Sơ AI chỉ tạo tệp để bạn tải về. Bạn tự in, ký và nộp; chúng tôi không nộp thay.
          </p>
        </div>
        <SourceNote source={spec.source} numberLabel="số hiệu" />
      </div>
    </div>
  );
}
