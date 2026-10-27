import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FormFiller } from "@/components/FormFiller";
import { getForm } from "@/lib/api";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const d = await getForm((await params).id);
  return { title: d ? `Điền ${d.spec.code} | Hồ Sơ AI` : "Hồ Sơ AI" };
}

export default async function FormPage({ params }: Props) {
  const detail = await getForm((await params).id);
  if (!detail) notFound();
  const { spec } = detail;
  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6">
      {spec.procedure_slugs[0] && (
        <Link
          href={`/procedure/${spec.procedure_slugs[0]}`}
          className="mt-8 inline-block text-sm text-muted hover:text-pen"
        >
          Quay lại thủ tục
        </Link>
      )}
      <h1 className="mt-4 font-serif text-3xl font-semibold leading-tight">
        {spec.title} <span className="text-muted">({spec.code})</span>
      </h1>
      <div className="mt-8">
        <FormFiller detail={detail} />
      </div>
    </main>
  );
}
