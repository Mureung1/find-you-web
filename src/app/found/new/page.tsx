import type { Metadata } from "next";
import { ItemForm } from "@/components/find-you/item-form";

export const metadata: Metadata = { title: "습득물 비공개 등록" };

export default function NewFoundItem() {
  return <ItemForm mode="found" />;
}
