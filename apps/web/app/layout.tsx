import type { Metadata } from "next";
import { Be_Vietnam_Pro, Noto_Serif } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const ui = Be_Vietnam_Pro({
  variable: "--font-ui",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

const official = Noto_Serif({
  variable: "--font-official",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "Hồ Sơ AI",
  description:
    "Tìm thủ tục hành chính, xem hồ sơ cần chuẩn bị, mọi thông tin đều dẫn nguồn chính thức.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className={`${ui.variable} ${official.variable} antialiased`}>
        <header className="mx-auto flex max-w-3xl items-baseline justify-between px-4 pt-6 sm:px-6">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Hồ Sơ <span className="text-pen">AI</span>
          </Link>
          <Link href="/profile" className="text-sm font-semibold text-muted hover:text-pen">
            Hồ sơ cá nhân
          </Link>
        </header>
        {children}
        <footer className="mx-auto max-w-3xl px-4 pb-10 pt-16 text-sm text-muted sm:px-6">
          Hồ Sơ AI không nộp hồ sơ thay bạn. Thông tin lấy từ cổng dịch vụ công chính thức; hãy
          kiểm tra lại tại nguồn trước khi nộp.
        </footer>
      </body>
    </html>
  );
}
