import type { Metadata } from "next";
import { SiteHeader } from "@/components/find-you/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Find you | 분실물 찾기", template: "%s | Find you" },
  description: "동네에서 잃어버린 물건을 찾고, 분실물과 습득물을 등록하세요.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full">
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
