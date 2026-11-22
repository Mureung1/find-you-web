import type { Metadata } from "next";
import { ItemForm } from "@/components/find-you/item-form";

export const metadata: Metadata = { title: "특징으로 찾기" };

export default function Match() {
  return <ItemForm mode="match" />;
}
