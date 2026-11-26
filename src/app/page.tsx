import { LostExplorer } from "@/components/find-you/lost-explorer";
import { backendOrigin } from "@/lib/backend-origin";
import type { LostItem } from "@/lib/find-you";

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
  return <LostExplorer initialItems={initialItems} />;
}
