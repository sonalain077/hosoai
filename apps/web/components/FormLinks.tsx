import Link from "next/link";

import { listForms } from "@/lib/api";

/** Forms we can fill for this procedure. Renders nothing if none (or the API is down). */
export async function FormLinks({ slug }: { slug: string }) {
  const forms = await listForms().catch(() => []);
  const mine = forms.filter((f) => f.procedure_slugs.includes(slug));
  if (mine.length === 0) return null;
  return (
    <ul className="mt-4 space-y-2">
      {mine.map((f) => (
        <li key={f.id}>
          <Link
            href={`/forms/${f.id}`}
            className="inline-block rounded-sm bg-pen px-4 py-2 font-semibold text-sheet"
          >
            Điền tờ khai {f.code}
          </Link>
        </li>
      ))}
    </ul>
  );
}
