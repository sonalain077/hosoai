import Link from "next/link";

import { AskForm } from "@/components/AskForm";
import { listProcedures } from "@/lib/api";
import type { ProcedureSummary } from "@/lib/types";

export default async function Home() {
  let procedures: ProcedureSummary[] | null = null;
  try {
    procedures = await listProcedures();
  } catch {
    procedures = null;
  }

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6">
      <h1 className="mt-14 text-4xl font-semibold leading-[1.1] tracking-tight sm:mt-20 sm:text-6xl">
        Bạn cần làm thủ tục gì?
      </h1>
      <p className="mt-4 max-w-prose text-lg text-muted">
        Kể bằng lời của bạn. Chúng tôi tìm đúng thủ tục, liệt kê giấy tờ, các bước, thời hạn và lệ
        phí, kèm đường dẫn tới trang chính thức cho từng mục.
      </p>

      <div className="mt-10">
        <AskForm />
      </div>

      <section className="mt-20" aria-labelledby="all">
        <h2 id="all" className="text-xl font-semibold">
          Các thủ tục hiện có
        </h2>
        {procedures === null ? (
          <p className="mt-3 text-muted">Không tải được danh sách. Kiểm tra API đang chạy.</p>
        ) : (
          <ul className="mt-4 grid gap-x-8 sm:grid-cols-2">
            {procedures.map((p) => (
              <li key={p.slug} className="border-t border-rule">
                <Link href={`/procedure/${p.slug}`} className="block py-3 hover:text-pen">
                  <span className="line-clamp-2">{p.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
