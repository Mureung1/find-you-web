import type { Metadata } from "next";
import { ItemForm } from "@/components/find-you/item-form";

export const metadata: Metadata = { title: "분실물 등록" };

export default function NewLostItem() {
  return <ItemForm mode="lost" />;
}
