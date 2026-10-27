"use client";

import { useState } from "react";

import { saveProfile } from "@/lib/api";
import { filledCount, normalizeProfile, PROFILE_FIELDS } from "@/lib/profile";
import type { Profile } from "@/lib/types";

export function ProfileForm({ initial }: { initial: Profile }) {
  const [profile, setProfile] = useState<Profile>(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const set = (key: keyof Profile, value: string) => {
    setProfile((p) => ({ ...p, [key]: value }));
    setState("idle");
  };

  async function submit() {
    setState("saving");
    try {
      setProfile(await saveProfile(normalizeProfile(profile)));
      setState("saved");
    } catch {
      setState("error");
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className="rounded-sm bg-sheet px-5 py-6 shadow-[0_1px_0_var(--rule)] sm:px-7"
    >
      <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
        {PROFILE_FIELDS.map((f) => (
          <div key={f.key} className={f.wide ? "sm:col-span-2" : ""}>
            <label htmlFor={f.key} className="block text-muted">
              {f.label}
              {f.hint && <span className="ml-2 text-sm opacity-70">{f.hint}</span>}
            </label>
            {f.type === "sex" ? (
              <select
                id={f.key}
                value={profile.sex ?? ""}
                onChange={(e) => set(f.key, e.target.value)}
                className="form-lines w-full bg-transparent text-lg text-pen focus:outline-none"
              >
                <option value="">—</option>
                <option value="Nam">Nam</option>
                <option value="Nữ">Nữ</option>
              </select>
            ) : (
              <input
                id={f.key}
                type={f.type ?? "text"}
                value={profile[f.key] ?? ""}
                onChange={(e) => set(f.key, e.target.value)}
                autoComplete="off"
                className="form-lines w-full bg-transparent text-lg text-pen focus:outline-none"
              />
            )}
          </div>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-5">
        <p className="text-sm text-muted" aria-live="polite">
          {state === "saved" && "Đã lưu. "}
          {state === "error" && "Không lưu được. Kiểm tra lại các ô và API. "}
          Đã điền {filledCount(profile)}/{PROFILE_FIELDS.length} mục.
        </p>
        <button
          type="submit"
          disabled={state === "saving"}
          className="rounded-sm bg-pen px-5 py-2.5 font-semibold text-sheet disabled:opacity-40"
        >
          {state === "saving" ? "Đang lưu…" : "Lưu hồ sơ"}
        </button>
      </div>
    </form>
  );
}
