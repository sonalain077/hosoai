import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DocumentChecklist } from "@/components/DocumentChecklist";
import { FormLinks } from "@/components/FormLinks";
import { ItemSource, SourceNote } from "@/components/SourceNote";
import { getProcedure } from "@/lib/api";
import { citesOtherPage, stripStepPrefix } from "@/lib/format";
import type { Procedure, Source, SourcedText } from "@/lib/types";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await getProcedure((await params).slug);
  return { title: p ? `${p.title} | Hồ Sơ AI` : "Hồ Sơ AI" };
}

export default async function ProcedurePage({ params }: Props) {
  const p = await getProcedure((await params).slug);
  if (!p) notFound();

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6">
      <Link href="/" className="mt-8 inline-block text-sm text-muted hover:text-pen">
        Tìm thủ tục khác
      </Link>

      <h1 className="mt-6 font-serif text-3xl font-semibold leading-tight sm:text-4xl">
        {p.title}
      </h1>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-muted">
        {p.national_code && (
          <>
            <dt>Mã thủ tục</dt>
            <dd className="text-ink">{p.national_code}</dd>
          </>
        )}
        {p.agency && (
          <>
            <dt>Nơi giải quyết</dt>
            <dd className="text-ink">{p.agency.text}</dd>
          </>
        )}
        {p.methods.length > 0 && (
          <>
            <dt>Cách nộp</dt>
            <dd className="text-ink">{p.methods.map((m) => m.text).join(", ")}</dd>
          </>
        )}
      </dl>
      <SourceNote source={p.source} />
      <FormLinks slug={p.slug} />

      {p.warnings.length > 0 && (
        <aside className="mt-8 border-l-4 border-stamp bg-sheet py-3 pl-4 pr-3">
          <p className="font-semibold text-stamp">Lưu ý về nguồn</p>
          <ul className="mt-1 list-disc pl-5">
            {p.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </aside>
      )}

      <Section title="Giấy tờ cần chuẩn bị" gloss="Documents to bring">
        {p.documents.length > 0 ? (
          <DocumentChecklist docs={p.documents} page={p.source} />
        ) : (
          <Unknown />
        )}
      </Section>

      <Section title="Các bước" gloss="Steps">
        {p.steps.length > 0 ? (
          <ol className="space-y-4">
            {p.steps.map((s, i) => (
              <li key={i} className="grid grid-cols-[2rem_1fr]">
                <span className="text-2xl font-semibold leading-none text-pen">{i + 1}</span>
                <Official item={s} page={p.source} text={stripStepPrefix(s.text)} />
              </li>
            ))}
          </ol>
        ) : (
          <Unknown />
        )}
      </Section>

      <div className="grid gap-x-10 sm:grid-cols-2">
        <Section title="Thời hạn giải quyết" gloss="Processing time">
          <Single item={p.processing_time} page={p.source} />
        </Section>
        <Section title="Phí, lệ phí" gloss="Fees">
          <Single item={p.fee} page={p.source} />
        </Section>
      </div>

      <Section title="Điều kiện" gloss="Who can apply">
        <Single item={p.conditions} page={p.source} />
      </Section>

      <Section title="Kết quả nhận được" gloss="What you receive">
        <Single item={p.result} page={p.source} />
      </Section>

      <Forms p={p} />

      <Section title="Căn cứ pháp lý" gloss="Legal basis">
        {p.legal_basis.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5">
            {p.legal_basis.map((l, i) => (
              <li key={i}>
                <Official item={l} page={p.source} />
              </li>
            ))}
          </ul>
        ) : (
          <Unknown />
        )}
      </Section>

      <div className="mt-14 border-t border-rule pt-4">
        <SourceNote source={p.source} />
      </div>
    </main>
  );
}

function Section({
  title,
  gloss,
  children,
}: {
  title: string;
  gloss: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">
        {title} <span className="text-base font-normal text-muted">{gloss}</span>
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** Verbatim text from the official page, set in the serif face. */
function Official({ item, page, text }: { item: SourcedText; page: Source; text?: string }) {
  return (
    <p className="whitespace-pre-line font-serif leading-relaxed">
      {text ?? item.text}
      {citesOtherPage(item.source, page) && <ItemSource source={item.source} />}
    </p>
  );
}

function Single({ item, page }: { item: SourcedText | null; page: Source }) {
  return item ? <Official item={item} page={page} /> : <Unknown />;
}

function Unknown() {
  return <p className="text-muted">Trang chính thức không ghi mục này. Chúng tôi không đoán.</p>;
}

function Forms({ p }: { p: Procedure }) {
  if (p.forms.length === 0) return null;
  return (
    <Section title="Biểu mẫu" gloss="Official forms">
      <ul className="space-y-2">
        {p.forms.map((f, i) => (
          <li key={i}>
            <a
              href={f.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-serif text-pen underline underline-offset-4"
            >
              {f.label}
            </a>
          </li>
        ))}
      </ul>
    </Section>
  );
}
