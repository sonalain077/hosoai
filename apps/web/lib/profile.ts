import type { Profile } from "./types";

type Field = {
  key: keyof Profile;
  label: string;
  hint?: string;
  type?: "text" | "date" | "email" | "tel" | "sex";
  wide?: boolean;
};

/** Profile fields, in the order Vietnamese forms usually ask for them. */
export const PROFILE_FIELDS: Field[] = [
  { key: "full_name", label: "Họ, chữ đệm và tên", hint: "Full name", wide: true },
  { key: "date_of_birth", label: "Ngày, tháng, năm sinh", hint: "Date of birth", type: "date" },
  { key: "sex", label: "Giới tính", hint: "Sex", type: "sex" },
  { key: "id_number", label: "Số định danh cá nhân", hint: "12-digit ID number" },
  { key: "passport_number", label: "Số hộ chiếu", hint: "Passport number" },
  { key: "nationality", label: "Quốc tịch", hint: "Nationality" },
  { key: "ethnicity", label: "Dân tộc", hint: "Ethnicity" },
  { key: "religion", label: "Tôn giáo", hint: "Religion" },
  { key: "occupation", label: "Nghề nghiệp", hint: "Occupation" },
  { key: "place_of_birth", label: "Nơi sinh", hint: "Place of birth", wide: true },
  { key: "hometown", label: "Quê quán", hint: "Hometown", wide: true },
  { key: "permanent_address", label: "Nơi thường trú", hint: "Permanent address", wide: true },
  { key: "current_address", label: "Nơi ở hiện tại", hint: "Current address", wide: true },
  { key: "phone", label: "Số điện thoại", hint: "Phone", type: "tel" },
  { key: "email", label: "Email", type: "email" },
];

/** Empty strings become null so the backend stores "not given", not "". */
export function normalizeProfile(p: Profile): Profile {
  const out = { ...p };
  for (const k of Object.keys(out) as (keyof Profile)[]) {
    const v = out[k];
    if (typeof v === "string" && v.trim() === "") (out as Record<string, unknown>)[k] = null;
    else if (typeof v === "string") (out as Record<string, unknown>)[k] = v.trim();
  }
  return out;
}

export function filledCount(p: Profile): number {
  return PROFILE_FIELDS.filter((f) => p[f.key] !== null && p[f.key] !== "").length;
}
