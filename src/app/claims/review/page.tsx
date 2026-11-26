import type { Metadata } from "next";
import { ReviewPanel } from "@/components/find-you/review-panel";
import styles from "@/components/find-you/management.module.css";

export const metadata: Metadata = { title: "소유 확인 검토" };

export default function ReviewPage() {
  return (
    <main className={["shell form-page", styles.page].join(" ")}>
      <div className="form-intro"><h1>소유 확인 검토</h1></div>
      <ReviewPanel />
    </main>
  );
}
