import { Backpack, CreditCard, Headphones, Package, Shirt, Umbrella, Wallet } from "lucide-react";

export const categories = {
  electronics: { label: "전자기기", icon: Headphones },
  wallet: { label: "지갑", icon: Wallet },
  card: { label: "카드·신분증", icon: CreditCard },
  accessory: { label: "생활용품", icon: Umbrella },
  clothing: { label: "의류·잡화", icon: Shirt },
  bag: { label: "가방", icon: Backpack },
  other: { label: "기타", icon: Package },
};

export type Category = keyof typeof categories;

export interface Location {
  location_id: string;
  region: string;
  dong: string;
}

export interface LostItem {
  item_id: string;
  title: string;
  category: Category;
  location: Location;
  event_date: string;
  status: "searching" | "returned";
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export async function requestApi<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, { cache: "no-store", ...options });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const message = typeof error?.detail === "string" ? error.detail : "요청을 처리하지 못했습니다.";
    throw new ApiError(response.status, message);
  }
  return response.json();
}

export function postApi<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  return requestApi<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
