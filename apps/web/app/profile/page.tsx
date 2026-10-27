import type { Metadata } from "next";

import { ProfileForm } from "@/components/ProfileForm";
import { getProfile } from "@/lib/api";

export const metadata: Metadata = { title: "Hồ sơ cá nhân | Hồ Sơ AI" };

export default async function ProfilePage() {
  let profile = null;
  try {
    profile = await getProfile();
  } catch {
    profile = null;
  }
  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6">
      <h1 className="mt-14 text-4xl font-semibold tracking-tight">Hồ sơ cá nhân</h1>
      <p className="mt-3 max-w-prose text-muted">
        Điền một lần, dùng lại để điền sẵn các tờ khai. Thông tin chỉ lưu trên máy này. Trợ lý chỉ
        biết tuổi và quốc tịch của bạn, không biết tên hay số giấy tờ. Bỏ trống mục nào cũng được.
      </p>
      <div className="mt-8">
        {profile ? (
          <ProfileForm initial={profile} />
        ) : (
          <p className="border-l-4 border-stamp pl-4">
            Không tải được hồ sơ. Kiểm tra API đang chạy.
          </p>
        )}
      </div>
    </main>
  );
}
