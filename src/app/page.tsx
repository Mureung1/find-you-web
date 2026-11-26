import { LostExplorer } from "@/components/find-you/lost-explorer";
import { backendOrigin } from "@/lib/backend-origin";
import type { LostItem } from "@/lib/find-you";
import localFont from "next/font/local";

const notoSans = localFont({
  src: "../components/find-you/fonts/noto-sans-kr.woff2",
  weight: "100 900",
  display: "swap",
  preload: false,
  variable: "--font-stitch-korean",
  adjustFontFallback: false,
});

const materialSymbols = localFont({
  src: "../components/find-you/fonts/material-symbols.woff2",
  weight: "400",
  display: "block",
  variable: "--font-stitch-symbols",
  adjustFontFallback: false,
});

const seoulDate = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul", dateStyle: "short" });

async function loadInitialData<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${backendOrigin()}/api/${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3500),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

export default async function Home() {
  const initialItems = await loadInitialData<LostItem[]>("lost-items");
  return <LostExplorer initialItems={initialItems} date={seoulDate.format(new Date())}
    fontClasses={`${notoSans.variable} ${materialSymbols.variable}`} />;
}
