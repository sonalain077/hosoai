import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FormFiller } from "@/components/FormFiller";
import { getForm } from "@/lib/api";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ procedure?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const d = await getForm((await params).id);
  return { title: d ? `Điền ${d.spec.code} | Hồ Sơ AI` : "Hồ Sơ AI" };
}

export default async function FormPage({ params, searchParams }: Props) {
  const { procedure } = await searchParams;
  const detail = await getForm((await params).id, procedure);
  if (!detail) notFound();
  const { spec } = detail;
  const back = procedure && spec.procedure_slugs.includes(procedure) ? procedure : spec.procedure_slugs[0];
  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6">
      {back && (
        <Link
          href={`/procedure/${back}`}
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
