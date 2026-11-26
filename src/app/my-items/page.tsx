import type { Metadata } from "next";
import { MyItemsPanel } from "@/components/find-you/my-items-panel";
import styles from "@/components/find-you/management.module.css";

export const metadata: Metadata = { title: "내 글" };

export default function MyItemsPage() {
  return (
    <main className={["shell form-page", styles.page].join(" ")}>
      <div className="form-intro"><h1>내 글</h1></div>
      <MyItemsPanel />
    </main>
  );
}
