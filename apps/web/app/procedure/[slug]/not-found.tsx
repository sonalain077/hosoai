import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6">
      <h1 className="mt-16 text-3xl font-semibold">Chưa có trong nguồn chính thức</h1>
      <p className="mt-3 max-w-prose text-muted">
        Thủ tục này không có trong các trang chính thức chúng tôi đang dùng, nên chúng tôi không hiển
        thị thông tin nào về nó.
      </p>
      <Link href="/" className="mt-6 inline-block font-semibold text-pen underline">
        Tìm thủ tục khác
      </Link>
    </main>
  );
}
